"""Matrix engine: rows (documents) × columns (questions) → grid of cited cells.

Fan out N*M cell jobs with bounded concurrency, yielding CellResults in
completion order so the UI can render cells as they finish instead of
waiting on a slow cell to block fast ones.

Why bounded concurrency:
  - OpenAI's Tier-1 TPM limits cap throughput regardless of how many
    sockets we open. Five concurrent cells is well under the 200k-TPM
    completion limit at default chunk sizes.
  - Postgres also caps connections; the engine reuses one ChunkAgent
    across all cells but each cell takes one transient session.

Partial-result tolerance: a failing cell becomes status="error" with a
parseable reason. The matrix yields that cell and keeps going; one bad
filing or one rate-limit doesn't poison the grid.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

from src.agents import CellAgent, CellResult
from src.core.logging import get_logger

log = get_logger(__name__)

DEFAULT_MAX_CONCURRENCY = 5


@dataclass(frozen=True)
class Question:
    """One column header. id is a stable string the frontend uses as a
    dict key; text is the natural-language prompt the agent sees."""
    id: str
    text: str


async def run_matrix(
    doc_ids: list[str],
    questions: list[Question],
    *,
    k: int = 5,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    agent: CellAgent | None = None,
) -> AsyncIterator[CellResult]:
    """Yield CellResults as each (doc, question) cell completes.

    Order is completion order, NOT input order — callers that need a
    grid layout should index by (doc_id, question_id) on receipt.
    """
    if not doc_ids or not questions:
        return

    agent = agent or CellAgent()
    sem = asyncio.Semaphore(max_concurrency)

    async def run_one(doc_id: str, q: Question) -> CellResult:
        async with sem:
            # CellAgent.answer_cell is sync (OpenAI sync SDK + DB session).
            # Run it in a thread so the semaphore actually limits parallel
            # work, not just parallel scheduling.
            return await asyncio.to_thread(
                agent.answer_cell,
                doc_id=doc_id,
                question=q.text,
                question_id=q.id,
                k=k,
            )

    tasks = [
        asyncio.create_task(run_one(doc_id, q))
        for doc_id in doc_ids
        for q in questions
    ]

    log.info(
        "matrix.start",
        docs=len(doc_ids),
        questions=len(questions),
        cells=len(tasks),
        max_concurrency=max_concurrency,
    )

    completed = 0
    try:
        for fut in asyncio.as_completed(tasks):
            result = await fut
            completed += 1
            log.info(
                "matrix.cell_complete",
                completed=completed,
                total=len(tasks),
                doc_id=result.doc_id,
                question_id=result.question_id,
                status=result.status,
            )
            yield result
    finally:
        # If the consumer aborts (HTTP client disconnects, etc.) cancel
        # any still-running tasks so we don't keep paying OpenAI for
        # answers no one will read.
        for t in tasks:
            if not t.done():
                t.cancel()
