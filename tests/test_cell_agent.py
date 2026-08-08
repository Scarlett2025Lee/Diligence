"""Cell agent unit tests.

Mock OpenAI + hybrid_search + budget bookkeeping so the suite stays
offline. We test:
  - happy path (answer + citations resolve back to retrieved hits)
  - JSON parse errors return a `status="error"` cell, not a raise
  - LLM citing a chunk id that wasn't retrieved is dropped silently
  - empty retrieval short-circuits before any LLM call
  - cost = input*price + output*price for the configured model
  - prompt envelope numbers the passages with chunk_id markers
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.agents.cell_agent import (
    COMPLETION_PRICING_USD_PER_1M,
    CellAgent,
    CellResult,
    _parse_response,
)
from src.retrieval import Hit


def _hit(chunk_id: int, item: str = "1A", text: str = "passage body") -> Hit:
    return Hit(
        chunk_id=chunk_id,
        doc_id="acc-1",
        item=item,
        section_title="Risk Factors",
        text=text,
        body_start=0,
        body_end=len(text),
        score=0.5,
        bm25_rank=1,
        dense_rank=2,
    )


def _make_agent() -> CellAgent:
    return CellAgent(client=MagicMock(), embedder=MagicMock())


def _stub_completion(content: str, prompt_tokens: int = 1200, completion_tokens: int = 80):
    """Returns a fake `chat.completions.create` response object."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ),
    )


def _stub_budget_and_logging():
    """No-op the DB-touching helpers at the cell_agent import site."""
    return patch.multiple(
        "src.agents.cell_agent",
        guard_budget=MagicMock(),
        log_llm_usage=MagicMock(),
    )


# ---- _parse_response (pure) --------------------------------------------------


def test_parse_response_extracts_answer_and_citations():
    raw = json.dumps({"answer": "Revenue was $391B.", "cited_chunk_ids": [42, 17]})
    answer, cited = _parse_response(raw)
    assert answer == "Revenue was $391B."
    assert cited == [42, 17]


def test_parse_response_strips_whitespace():
    raw = json.dumps({"answer": "  trimmed  ", "cited_chunk_ids": []})
    answer, _ = _parse_response(raw)
    assert answer == "trimmed"


def test_parse_response_rejects_non_json():
    with pytest.raises(ValueError, match="non-JSON"):
        _parse_response("Sorry, I cannot do that.")


def test_parse_response_rejects_missing_answer():
    raw = json.dumps({"cited_chunk_ids": [1]})
    with pytest.raises(ValueError, match="missing 'answer'"):
        _parse_response(raw)


def test_parse_response_rejects_non_int_citations():
    raw = json.dumps({"answer": "x", "cited_chunk_ids": ["nope"]})
    with pytest.raises(ValueError, match="list\\[int\\]"):
        _parse_response(raw)


# ---- happy path -------------------------------------------------------------


def test_answer_cell_happy_path_returns_done_with_resolved_citations():
    agent = _make_agent()
    hits = [_hit(11, text="Total net sales were $391 billion."), _hit(12, item="7")]
    llm_reply = json.dumps({
        "answer": "Total net sales were $391 billion in fiscal 2024.",
        "cited_chunk_ids": [11],
    })
    agent._client.chat.completions.create.return_value = _stub_completion(llm_reply)

    with patch("src.agents.cell_agent.hybrid_search", return_value=hits), \
         _stub_budget_and_logging():
        result = agent.answer_cell("acc-1", "What was revenue?", question_id="q-rev")

    assert isinstance(result, CellResult)
    assert result.status == "done"
    assert result.answer == "Total net sales were $391 billion in fiscal 2024."
    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == 11
    assert result.citations[0].quote == "Total net sales were $391 billion."
    assert result.cost_usd > 0
    assert result.latency_ms >= 0
    assert result.error is None


def test_answer_cell_drops_citations_not_in_retrieved_hits():
    agent = _make_agent()
    hits = [_hit(11), _hit(12)]
    # LLM cites 11 (real) and 999 (not retrieved) — only 11 should survive.
    llm_reply = json.dumps({"answer": "stuff", "cited_chunk_ids": [11, 999]})
    agent._client.chat.completions.create.return_value = _stub_completion(llm_reply)

    with patch("src.agents.cell_agent.hybrid_search", return_value=hits), \
         _stub_budget_and_logging():
        result = agent.answer_cell("acc-1", "q")

    assert [c.chunk_id for c in result.citations] == [11]


def test_answer_cell_preserves_llm_citation_order():
    agent = _make_agent()
    hits = [_hit(11), _hit(12), _hit(13)]
    llm_reply = json.dumps({"answer": "x", "cited_chunk_ids": [13, 11]})
    agent._client.chat.completions.create.return_value = _stub_completion(llm_reply)

    with patch("src.agents.cell_agent.hybrid_search", return_value=hits), \
         _stub_budget_and_logging():
        result = agent.answer_cell("acc-1", "q")

    assert [c.chunk_id for c in result.citations] == [13, 11]


# ---- error paths ------------------------------------------------------------


def test_answer_cell_no_retrieval_hits_returns_error_without_calling_llm():
    agent = _make_agent()
    with patch("src.agents.cell_agent.hybrid_search", return_value=[]), \
         _stub_budget_and_logging():
        result = agent.answer_cell("acc-1", "q")
    assert result.status == "error"
    assert "no retrieval hits" in (result.error or "")
    agent._client.chat.completions.create.assert_not_called()


def test_answer_cell_llm_returns_malformed_json_yields_error_cell():
    agent = _make_agent()
    hits = [_hit(11)]
    agent._client.chat.completions.create.return_value = _stub_completion(
        "Sorry, I cannot do that."
    )
    with patch("src.agents.cell_agent.hybrid_search", return_value=hits), \
         _stub_budget_and_logging():
        result = agent.answer_cell("acc-1", "q")
    assert result.status == "error"
    assert "completion failed" in (result.error or "")


def test_answer_cell_retrieval_failure_yields_error_cell():
    agent = _make_agent()
    with patch("src.agents.cell_agent.hybrid_search", side_effect=RuntimeError("db down")), \
         _stub_budget_and_logging():
        result = agent.answer_cell("acc-1", "q")
    assert result.status == "error"
    assert "retrieval failed" in (result.error or "")
    assert "db down" in (result.error or "")


# ---- cost + prompt envelope --------------------------------------------------


def test_cost_for_tokens_uses_published_pricing_for_gpt_4o_mini():
    agent = _make_agent()
    assert agent._model == "gpt-4o-mini"
    in_price, out_price = COMPLETION_PRICING_USD_PER_1M["gpt-4o-mini"]
    # 1M input + 1M output should equal the sum of the two prices.
    assert agent._cost_for_tokens(1_000_000, 1_000_000) == pytest.approx(
        in_price + out_price
    )
    assert agent._cost_for_tokens(0, 0) == 0.0


def test_prompt_envelope_numbers_each_passage_with_chunk_id():
    agent = _make_agent()
    msgs = agent._build_messages(
        "Q?",
        [_hit(11, text="alpha"), _hit(12, item="7", text="beta")],
    )
    user_content = msgs[-1]["content"]
    assert "[11]" in user_content
    assert "[12]" in user_content
    assert "alpha" in user_content
    assert "beta" in user_content
    assert "Item 1A" in user_content
    assert "Item 7" in user_content
    assert "Question: Q?" in user_content
