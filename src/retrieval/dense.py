"""Dense vector search via pgvector cosine distance.

Single SELECT — `ORDER BY embedding <=> :q LIMIT k`. With the IVFFlat index
this is sub-linear; without it (small corpora) it's a sequential scan but
still under 50ms for ~10k vectors.

Chunks whose `embedding IS NULL` are filtered out by the WHERE clause —
backfill is responsible for populating them, retrieval skips them silently.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select

from src.storage.db import get_session
from src.storage.schema import ChunkRow


@dataclass(frozen=True)
class DenseHit:
    """Dense result. `distance` is cosine distance in [0, 2]; smaller is
    closer. We carry the ChunkRow directly so the matrix engine can quote
    text and resolve citation offsets without another query."""
    chunk: ChunkRow
    distance: float


def dense_search(
    query_vector: Sequence[float],
    doc_ids: list[str] | None,
    k: int,
) -> list[DenseHit]:
    """Return the top-k nearest chunks by cosine distance.

    `doc_ids=None` means search the whole corpus. Passing `[doc_id]` is the
    common case for cell-agent retrieval (one question x one document).
    """
    if k <= 0:
        return []
    distance = ChunkRow.embedding.cosine_distance(list(query_vector))
    stmt = (
        select(ChunkRow, distance.label("distance"))
        .where(ChunkRow.embedding.isnot(None))
        .order_by(distance)
        .limit(k)
    )
    if doc_ids:
        stmt = stmt.where(ChunkRow.doc_id.in_(doc_ids))
    with get_session() as session:
        rows = session.execute(stmt).all()
    return [DenseHit(chunk=row[0], distance=float(row[1])) for row in rows]
