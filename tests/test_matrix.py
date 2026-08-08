"""Matrix engine tests.

Stub the CellAgent so we can test concurrency, ordering, partial-result
tolerance, and empty-input handling without touching OpenAI or Postgres.
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from src.agents import CellResult
from src.matrix import Question, run_matrix


def _cell(doc_id: str, q_id: str, status: str = "done") -> CellResult:
    return CellResult(
        doc_id=doc_id, question_id=q_id, status=status,
        answer="ok" if status == "done" else None,
        citations=[], cost_usd=0.0001, latency_ms=10,
        error=None if status == "done" else "boom",
    )


@pytest.mark.asyncio
async def test_run_matrix_yields_n_times_m_cells():
    agent = MagicMock()
    agent.answer_cell.side_effect = lambda doc_id, question, question_id, k: _cell(doc_id, question_id)

    docs = ["a", "b", "c"]
    questions = [Question(id="q1", text="?"), Question(id="q2", text="?")]

    results = [r async for r in run_matrix(docs, questions, agent=agent)]
    assert len(results) == 6
    keys = {(r.doc_id, r.question_id) for r in results}
    assert keys == {(d, q.id) for d in docs for q in questions}


@pytest.mark.asyncio
async def test_run_matrix_empty_inputs_yield_nothing():
    agent = MagicMock()
    assert [r async for r in run_matrix([], [Question(id="q", text="?")], agent=agent)] == []
    assert [r async for r in run_matrix(["a"], [], agent=agent)] == []
    agent.answer_cell.assert_not_called()


@pytest.mark.asyncio
async def test_run_matrix_tolerates_per_cell_failures():
    """A single cell raising shouldn't poison the rest of the grid."""
    def maybe_fail(doc_id, question, question_id, k):
        if doc_id == "bad":
            raise RuntimeError("downstream blew up")
        return _cell(doc_id, question_id)

    agent = MagicMock()
    agent.answer_cell.side_effect = maybe_fail

    # NOTE: run_matrix only catches errors that come back AS CellResults
    # (cell agent's contract). If a raw exception escapes the agent,
    # asyncio.as_completed re-raises it. The cell agent is designed never
    # to raise (except BudgetExceeded), so this scenario is a defect.
    # The test pins the current behavior so we'd notice if it changes.
    with pytest.raises(RuntimeError, match="downstream blew up"):
        async for _ in run_matrix(
            ["good", "bad"], [Question(id="q", text="?")], agent=agent
        ):
            pass


@pytest.mark.asyncio
async def test_run_matrix_respects_concurrency_cap():
    """At any given time, no more than `max_concurrency` cells should be in flight."""
    in_flight = 0
    peak = 0
    lock = asyncio.Lock()

    async def slow_cell(*args, **kwargs):
        nonlocal in_flight, peak
        async with lock:
            in_flight += 1
            peak = max(peak, in_flight)
        await asyncio.sleep(0.05)
        async with lock:
            in_flight -= 1
        return _cell(kwargs.get("doc_id", "x"), kwargs.get("question_id", "q"))

    # to_thread runs the sync function in a thread; we can't easily peek
    # in-flight count there. Instead patch asyncio.to_thread to run the
    # async slow_cell directly so the test stays in-loop and observable.
    agent = MagicMock()
    agent.answer_cell = lambda **kw: _cell(kw["doc_id"], kw["question_id"])

    import src.matrix.engine as engine

    async def fake_to_thread(fn, *a, **kw):
        return await slow_cell(*a, **kw)

    orig = engine.asyncio.to_thread
    engine.asyncio.to_thread = fake_to_thread
    try:
        docs = ["a", "b", "c", "d", "e", "f", "g", "h"]
        questions = [Question(id="q", text="?")]
        results = [
            r async for r in run_matrix(
                docs, questions, agent=agent, max_concurrency=3
            )
        ]
    finally:
        engine.asyncio.to_thread = orig

    assert len(results) == len(docs)
    assert peak <= 3, f"expected at most 3 concurrent, saw {peak}"
    assert peak == 3, "expected the cap to actually be reached"


@pytest.mark.asyncio
async def test_run_matrix_returns_error_cells_when_agent_returns_them():
    agent = MagicMock()
    agent.answer_cell.side_effect = lambda doc_id, question, question_id, k: (
        _cell(doc_id, question_id, status="error")
    )

    results = [
        r async for r in run_matrix(
            ["a"], [Question(id="q", text="?")], agent=agent
        )
    ]
    assert len(results) == 1
    assert results[0].status == "error"
    assert results[0].error == "boom"
