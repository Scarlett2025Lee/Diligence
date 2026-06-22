"""Hybrid retrieval over chunked filings.

Public surface:
    from src.retrieval import hybrid_search, Hit

Strategy:
  1. BM25 (rank_bm25, in-process) — wins on exact terms (tickers,
     "Item 1A", dollar figures) which are everywhere in financial text.
  2. Dense (pgvector cosine) — wins on conceptual rephrasings.
  3. Reciprocal Rank Fusion combines both lists with one parameter-free
     formula (1 / (k + rank)) — robust baseline, no weights to tune.
"""
from src.retrieval.bm25 import bm25_search
from src.retrieval.dense import dense_search
from src.retrieval.hybrid import Hit, hybrid_search, rrf_fuse

__all__ = ["Hit", "bm25_search", "dense_search", "hybrid_search", "rrf_fuse"]
