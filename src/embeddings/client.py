"""OpenAI embedding client with budget, batching, and telemetry.

Why all the ceremony for a single API call:
  - **Exact token counts** via tiktoken, not the chunker's 4-chars/token
    estimate. The API rejects requests over its per-request token limit
    (300k for text-embedding-3-small), so we need a real number.
  - **Cost is computed and logged before write** so the daily-budget guard
    can refuse the call if it would push us over `DAILY_BUDGET_USD`. This
    is the line between "small mistake" and "I burned $5 on a bug".
  - **Every call writes an llm_usage row.** Eval, fine-tuning decisions,
    and the dashboard all key off that table. No row = call didn't happen.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

import tiktoken
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.budget import BudgetExceeded, guard_budget, log_llm_usage, spent_today
from src.core.config import get_settings
from src.core.logging import get_logger

log = get_logger(__name__)

# Re-export so callers that imported BudgetExceeded from here still work.
__all__ = ["BudgetExceeded", "EmbeddingClient", "PRICING_USD_PER_1M_TOKENS"]

# Prices in USD per 1M tokens. Source: OpenAI public pricing.
# When OpenAI ships a new model, add it here; the client will use whatever
# `settings.embedding_model` resolves to.
PRICING_USD_PER_1M_TOKENS: dict[str, float] = {
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
    "text-embedding-ada-002": 0.10,
}

# OpenAI's per-request limit for the text-embedding-3-* family.
_MAX_TOKENS_PER_REQUEST = 300_000
# Conservative ceiling on inputs per request — the API documents 2048.
_MAX_INPUTS_PER_REQUEST = 2048


@dataclass(frozen=True)
class EmbeddingBatch:
    """Result of one OpenAI request — vectors aligned with input order."""
    vectors: list[list[float]]
    input_tokens: int
    cost_usd: float
    latency_ms: int
    request_id: str


class EmbeddingClient:
    def __init__(self, client: OpenAI | None = None, encoding=None) -> None:
        s = get_settings()
        self._client = client or OpenAI(api_key=s.openai_api_key)
        self._model = s.embedding_model
        self._budget = s.daily_budget_usd
        # cl100k_base is the BPE used by all text-embedding-3-* models.
        # Injectable so tests don't trigger tiktoken's first-use download
        # of the encoder file. Production passes None and gets the real one.
        self._encoding = encoding or tiktoken.get_encoding("cl100k_base")

    # ----- public ------------------------------------------------------

    def count_tokens(self, text: str) -> int:
        return len(self._encoding.encode(text))

    def pack(self, texts: list[str]) -> list[list[int]]:
        """Greedy bin-pack input indexes into request-sized batches.

        Each returned inner list holds positions into `texts`. The caller
        embeds each batch with `embed_batch` and reassembles results by
        position. Splitting here (not inside embed_batch) keeps batching
        testable without the network.
        """
        sizes = [self.count_tokens(t) for t in texts]
        batches: list[list[int]] = []
        current: list[int] = []
        current_tokens = 0
        for i, n in enumerate(sizes):
            if n > _MAX_TOKENS_PER_REQUEST:
                # A single chunk over the per-request limit means the
                # chunker produced something out of contract. We refuse
                # rather than silently truncate — the caller should fix
                # the chunker, not lose data.
                raise ValueError(
                    f"Chunk at index {i} has {n} tokens, exceeds "
                    f"{_MAX_TOKENS_PER_REQUEST} per-request limit"
                )
            over_tokens = current_tokens + n > _MAX_TOKENS_PER_REQUEST
            over_count = len(current) >= _MAX_INPUTS_PER_REQUEST
            if current and (over_tokens or over_count):
                batches.append(current)
                current = []
                current_tokens = 0
            current.append(i)
            current_tokens += n
        if current:
            batches.append(current)
        return batches

    def embed_batch(self, texts: list[str]) -> EmbeddingBatch:
        """Embed a single batch. Budget-checked, retried, logged.

        Assumes the caller has already split inputs to fit one request.
        """
        if not texts:
            raise ValueError("embed_batch called with empty texts")
        input_tokens = sum(self.count_tokens(t) for t in texts)
        projected_cost = self._cost_for_tokens(input_tokens)
        self._guard_budget(projected_cost)

        request_id = uuid.uuid4().hex
        t0 = time.perf_counter()
        resp = self._call_openai(texts)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        # Prefer the API's reported usage; fall back to our local count
        # if the response shape drifts (it has changed once before).
        actual_tokens = getattr(getattr(resp, "usage", None), "prompt_tokens", input_tokens)
        cost = self._cost_for_tokens(actual_tokens)

        self._log_usage(
            request_id=request_id,
            tokens=actual_tokens,
            cost=cost,
            latency_ms=latency_ms,
        )
        log.info(
            "embedding.batch",
            request_id=request_id,
            model=self._model,
            inputs=len(texts),
            tokens=actual_tokens,
            cost_usd=round(cost, 6),
            latency_ms=latency_ms,
        )
        return EmbeddingBatch(
            vectors=[d.embedding for d in resp.data],
            input_tokens=actual_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            request_id=request_id,
        )

    # ----- internals ---------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def _call_openai(self, texts: list[str]):
        return self._client.embeddings.create(model=self._model, input=texts)

    def _cost_for_tokens(self, tokens: int) -> float:
        price = PRICING_USD_PER_1M_TOKENS.get(self._model)
        if price is None:
            raise KeyError(
                f"No price entry for embedding model {self._model!r}. "
                f"Add it to PRICING_USD_PER_1M_TOKENS."
            )
        return tokens * price / 1_000_000

    def _guard_budget(self, projected_cost: float) -> None:
        guard_budget(projected_cost, self._budget)

    def _log_usage(
        self, *, request_id: str, tokens: int, cost: float, latency_ms: int
    ) -> None:
        log_llm_usage(
            request_id=request_id,
            operation="embedding",
            model=self._model,
            input_tokens=tokens,
            output_tokens=0,
            cost_usd=cost,
            latency_ms=latency_ms,
        )


# Re-export so tests that patched src.embeddings.client._spent_today still work.
_spent_today = spent_today
