"""Embedding pipeline.

Two responsibilities:
  - `EmbeddingClient` calls OpenAI in batches, counts exact tokens with
    tiktoken, computes cost from the published price table, and writes one
    `llm_usage` row per request. It does NOT touch the chunks table — that
    keeps the client reusable for ad-hoc queries too.
  - `backfill_embeddings()` walks chunks where `embedding IS NULL`, hands
    them to the client in budget-respecting batches, and writes vectors
    back. Re-runnable any time — it's idempotent on chunk rows.
"""
from src.embeddings.client import (
    EmbeddingClient,
    PRICING_USD_PER_1M_TOKENS,
)
from src.embeddings.backfill import backfill_embeddings

__all__ = [
    "EmbeddingClient",
    "PRICING_USD_PER_1M_TOKENS",
    "backfill_embeddings",
]
