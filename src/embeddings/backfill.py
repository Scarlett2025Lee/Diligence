"""Backfill chunk vectors.

Walks every `chunks` row where `embedding IS NULL`, batches them with
`EmbeddingClient.pack`, embeds, and writes vectors back. Idempotent — only
re-touches NULL rows — so it's safe to re-run after a crash or rate-limit.

Why backfill instead of embedding at ingest time:
  - Decouples slow/paid step from parsing. Chunker tweaks don't burn money.
  - Lets us batch optimally across filings (a single 10-K's chunks rarely
    fill the API's per-request budget; mixed-filing batches do).
  - Keeps the ingest script fast for the eval-set / iteration loop.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from src.core.logging import get_logger
from src.embeddings.client import EmbeddingClient
from src.storage.db import get_session
from src.storage.schema import ChunkRow

log = get_logger(__name__)


@dataclass(frozen=True)
class BackfillStats:
    chunks_embedded: int
    batches: int
    total_tokens: int
    total_cost_usd: float


def backfill_embeddings(
    client: EmbeddingClient | None = None,
    limit: int | None = None,
) -> BackfillStats:
    """Embed all unembedded chunks. Returns aggregate stats.

    Args:
        client: inject for tests; otherwise the default client is used.
        limit:  stop after this many chunks are embedded (for smoke runs
                and for staying inside a small daily budget while iterating).
    """
    client = client or EmbeddingClient()

    pending_ids, pending_texts = _load_pending(limit)
    if not pending_ids:
        log.info("backfill.noop", reason="no chunks with NULL embedding")
        return BackfillStats(0, 0, 0, 0.0)

    log.info("backfill.start", chunks=len(pending_ids))

    batches = client.pack(pending_texts)
    total_tokens = 0
    total_cost = 0.0
    embedded = 0

    for batch_no, idxs in enumerate(batches):
        texts = [pending_texts[i] for i in idxs]
        result = client.embed_batch(texts)

        # Write vectors back in the same transaction so a mid-batch crash
        # leaves rows in a consistent state (either embedded + logged, or
        # neither — never embedded-without-cost or cost-without-vector).
        with get_session() as session:
            for i, vec in zip(idxs, result.vectors):
                row = session.get(ChunkRow, pending_ids[i])
                if row is not None:  # guard against concurrent deletion
                    row.embedding = vec

        total_tokens += result.input_tokens
        total_cost += result.cost_usd
        embedded += len(idxs)
        log.info(
            "backfill.batch_done",
            batch=batch_no,
            embedded=embedded,
            total_cost_usd=round(total_cost, 6),
        )

    return BackfillStats(
        chunks_embedded=embedded,
        batches=len(batches),
        total_tokens=total_tokens,
        total_cost_usd=total_cost,
    )


def _load_pending(limit: int | None) -> tuple[list[int], list[str]]:
    with get_session() as session:
        stmt = (
            select(ChunkRow.id, ChunkRow.text)
            .where(ChunkRow.embedding.is_(None))
            .order_by(ChunkRow.id)
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        rows = session.execute(stmt).all()
    ids = [r.id for r in rows]
    texts = [r.text for r in rows]
    return ids, texts
