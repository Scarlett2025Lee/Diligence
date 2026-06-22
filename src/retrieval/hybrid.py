"""Hybrid retrieval: BM25 + dense, fused with Reciprocal Rank Fusion.

The cell agent calls `hybrid_search(question, doc_ids, k)` and gets back
the top-k chunks with their fused score, BM25 rank, and dense rank.
Carrying the per-source ranks lets us debug retrieval failures from logs
("the right chunk was rank 8 in dense and not in BM25 at all") instead of
re-running the pipeline.

Why RRF and not weighted score sum:
  - BM25 scores and cosine distances are on incomparable scales.
    Normalizing them is fiddly and breaks across corpora.
  - RRF takes only ranks, so it's parameter-free (modulo k_const=60).
  - Empirically competitive with learned fusion on most IR benchmarks.

The function embeds the question once via EmbeddingClient — that's one
extra OpenAI call per question (~$0.00001 at text-embedding-3-small).
Cheap enough to do at query time; caching is a Phase-2 nicety.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select

from src.core.logging import get_logger
from src.embeddings.client import EmbeddingClient
from src.retrieval.bm25 import bm25_search
from src.retrieval.dense import dense_search
from src.storage.db import get_session
from src.storage.schema import ChunkRow

log = get_logger(__name__)

DEFAULT_RRF_K = 60      # Standard value from the original RRF paper.
DEFAULT_OVERFETCH = 4   # Fetch k*OVERFETCH from each source before fusing.


@dataclass(frozen=True)
class Hit:
    """One fused retrieval result. `chunk_id` is the canonical id; the
    cell agent reads the full ChunkRow if it needs body text. Ranks are
    1-indexed (rank 1 = best); None means the chunk didn't appear in
    that source at all."""
    chunk_id: int
    doc_id: str
    item: str
    section_title: str
    text: str
    body_start: int
    body_end: int
    score: float
    bm25_rank: int | None
    dense_rank: int | None


def rrf_fuse(
    rankings: list[list[int]],
    k_const: int = DEFAULT_RRF_K,
) -> list[tuple[int, float]]:
    """Combine multiple rank lists into one. Returns [(item_id, score)] sorted.

    Each input list is best-first; items not in a list contribute 0 from
    that source. The standard RRF formula:
        score(d) = sum_i  1 / (k_const + rank_i(d))
    where rank_i is 1-indexed and rank_i = infinity for items missing
    from list i.
    """
    scores: dict[int, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] += 1.0 / (k_const + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


def hybrid_search(
    question: str,
    doc_ids: list[str] | None = None,
    k: int = 10,
    *,
    embedder: EmbeddingClient | None = None,
    rrf_k_const: int = DEFAULT_RRF_K,
    overfetch: int = DEFAULT_OVERFETCH,
) -> list[Hit]:
    """Return the top-k chunks for `question`, filtered to `doc_ids`.

    Over-fetches `k * overfetch` from each source so the fusion has enough
    overlap to make ranking decisions; cuts back to `k` after.
    """
    embedder = embedder or EmbeddingClient()

    # Embed the question once. Same client = same telemetry table.
    query_vector = embedder.embed_batch([question]).vectors[0]

    fetch_k = max(k * overfetch, k)
    candidate_chunks = _load_chunks(doc_ids)

    bm25_hits = bm25_search(question, candidate_chunks, k=fetch_k)
    dense_hits = dense_search(query_vector, doc_ids, k=fetch_k)

    bm25_ids = [h.chunk.id for h in bm25_hits]
    dense_ids = [h.chunk.id for h in dense_hits]

    fused = rrf_fuse([bm25_ids, dense_ids], k_const=rrf_k_const)

    bm25_rank = {cid: r for r, cid in enumerate(bm25_ids, start=1)}
    dense_rank = {cid: r for r, cid in enumerate(dense_ids, start=1)}
    chunks_by_id: dict[int, ChunkRow] = {h.chunk.id: h.chunk for h in bm25_hits}
    for h in dense_hits:
        chunks_by_id.setdefault(h.chunk.id, h.chunk)

    hits: list[Hit] = []
    for chunk_id, score in fused[:k]:
        c = chunks_by_id[chunk_id]
        hits.append(
            Hit(
                chunk_id=c.id,
                doc_id=c.doc_id,
                item=c.item,
                section_title=c.section_title,
                text=c.text,
                body_start=c.body_start,
                body_end=c.body_end,
                score=score,
                bm25_rank=bm25_rank.get(chunk_id),
                dense_rank=dense_rank.get(chunk_id),
            )
        )

    log.info(
        "retrieval.hybrid",
        question_chars=len(question),
        doc_ids=doc_ids,
        k=k,
        bm25_returned=len(bm25_ids),
        dense_returned=len(dense_ids),
        fused_returned=len(hits),
    )
    return hits


def _load_chunks(doc_ids: list[str] | None) -> list[ChunkRow]:
    """Pull the candidate chunks for BM25 scoring.

    BM25 is in-process: we score against whatever subset the caller
    cares about. For cell retrieval that's a single filing; for global
    search we pull everything (acceptable up to ~tens of thousands of
    chunks; revisit when the corpus grows).
    """
    with get_session() as session:
        stmt = select(ChunkRow)
        if doc_ids:
            stmt = stmt.where(ChunkRow.doc_id.in_(doc_ids))
        return list(session.execute(stmt).scalars())
