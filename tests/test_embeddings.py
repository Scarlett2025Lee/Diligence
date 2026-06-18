"""Embedding client unit tests.

We mock OpenAI, inject a fake tokenizer, and stub the LLM-usage row insert
so the suite stays network-free and DB-free. The contract under test:
  - Token counts come from the injected encoder (tiktoken in prod).
  - Batches respect per-request token AND input-count limits.
  - Cost = tokens * pricing / 1e6.
  - BudgetExceeded fires before the API call.
  - Refuses an over-limit single chunk rather than truncating.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.embeddings.client import (
    PRICING_USD_PER_1M_TOKENS,
    BudgetExceeded,
    EmbeddingClient,
)


class _FakeEncoding:
    """Whitespace tokenizer — one 'token' per word. Stable across platforms."""

    def encode(self, text: str) -> list[int]:
        return [0] * len(text.split())


def _make_client() -> EmbeddingClient:
    """EmbeddingClient with all I/O stubbed out."""
    mock_openai = MagicMock()
    client = EmbeddingClient(client=mock_openai, encoding=_FakeEncoding())
    # Default model is text-embedding-3-small; assert the price table covers it.
    assert client._model in PRICING_USD_PER_1M_TOKENS
    return client


def _stub_usage(spent_today: float = 0.0):
    """Patch the DB-touching helpers so the test never opens a session."""
    return patch.multiple(
        "src.embeddings.client",
        _spent_today=MagicMock(return_value=spent_today),
        get_session=MagicMock(),
    )


def test_count_tokens_delegates_to_encoder():
    client = _make_client()
    # Fake encoder is one-token-per-word.
    assert client.count_tokens("hello world") == 2
    assert client.count_tokens("a b c d e") == 5


def test_pack_groups_by_token_budget():
    client = _make_client()
    # Each entry well under the limit; should land in one batch.
    texts = ["hello world"] * 10
    batches = client.pack(texts)
    assert batches == [list(range(10))]


def test_pack_splits_when_input_count_exceeds_limit():
    client = _make_client()
    # Tiny texts so token budget doesn't bind; input-count limit (2048) does.
    texts = ["hi"] * 2500
    batches = client.pack(texts)
    assert len(batches) == 2
    assert sum(len(b) for b in batches) == 2500
    assert all(len(b) <= 2048 for b in batches)


def test_pack_rejects_single_input_over_request_limit():
    client = _make_client()
    huge = "token " * 200_000  # ~200k chars; cl100k_base will exceed 300k tokens
    # Force a count over the per-request limit regardless of tokenizer drift.
    with patch.object(client, "count_tokens", return_value=400_000):
        with pytest.raises(ValueError, match="exceeds"):
            client.pack([huge])


def test_cost_for_tokens_uses_published_price():
    client = _make_client()
    price = PRICING_USD_PER_1M_TOKENS["text-embedding-3-small"]
    assert client._cost_for_tokens(1_000_000) == pytest.approx(price)
    assert client._cost_for_tokens(0) == 0.0


def test_embed_batch_calls_openai_and_returns_aligned_vectors():
    client = _make_client()
    fake = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.1, 0.2]), SimpleNamespace(embedding=[0.3, 0.4])],
        usage=SimpleNamespace(prompt_tokens=4),
    )
    client._client.embeddings.create.return_value = fake

    with _stub_usage(spent_today=0.0):
        result = client.embed_batch(["hello world", "foo bar"])

    assert len(result.vectors) == 2
    assert result.vectors[0] == [0.1, 0.2]
    assert result.input_tokens == 4
    # 4 tokens * $0.02 / 1M
    assert result.cost_usd == pytest.approx(4 * 0.02 / 1_000_000)
    client._client.embeddings.create.assert_called_once()


def test_embed_batch_refuses_when_over_budget():
    client = _make_client()
    # Daily budget default is $5; pretend $4.9999 already spent, request
    # costs more than the slack.
    with _stub_usage(spent_today=4.9999):
        with patch.object(client, "count_tokens", return_value=1_000_000):
            with pytest.raises(BudgetExceeded):
                client.embed_batch(["very expensive text"])
    client._client.embeddings.create.assert_not_called()


def test_embed_batch_empty_input_raises():
    client = _make_client()
    with pytest.raises(ValueError, match="empty"):
        client.embed_batch([])
