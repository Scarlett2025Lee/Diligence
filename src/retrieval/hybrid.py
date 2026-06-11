"""Hybrid retrieval: BM25 + dense vectors, fused, then reranked.

Why hybrid for this corpus:
  - Financial text is full of exact terms (ticker symbols, 'covenant', 'Item 1A',
    dollar figures) where BM25 wins.
  - Conceptual questions ('how does management view margin pressure?') need dense.
Fusion: Reciprocal Rank Fusion (RRF) — simple, no tuning, strong baseline.
TODO(phase-1): implement BM25Index, VectorIndex (pgvector), rrf_fuse(), rerank().
"""
