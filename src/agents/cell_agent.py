"""Cell agent: one question × one document → cited answer.

This is the heart of the Hebbia-style product. Given (doc_id, question),
the agent:
  1. Runs hybrid_search to pull the top-k chunks from that filing.
  2. Sends those chunks to GPT-4o-mini with strict grounding instructions
     ("answer only from the provided passages; cite by chunk id").
  3. Parses the JSON response, resolves cited chunk ids back to Citation
     objects (with the exact quote + body offsets for the UI).
  4. Returns CellResult — the shape the frontend already renders.

Failure semantics:
  - Empty retrieval → status="error", error="no retrieval hits".
  - Budget exhausted → BudgetExceeded propagates (the matrix engine will
    catch and surface as a cell-level error).
  - LLM returns invalid JSON or unknown chunk ids → status="error" with
    a parseable reason; we'd rather show a red cell than a fabricated
    answer.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Literal

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.budget import guard_budget, log_llm_usage
from src.core.config import get_settings
from src.core.logging import get_logger
from src.embeddings.client import EmbeddingClient
from src.retrieval import Hit, hybrid_search

log = get_logger(__name__)

# Prices in USD per 1M tokens (input, output). Source: OpenAI pricing page.
COMPLETION_PRICING_USD_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o":      (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1":     (2.00, 8.00),
}

# Conservative ceiling for budget guard projection. The actual reply is
# almost always shorter, but we want the guard to refuse pessimistically.
_MAX_OUTPUT_TOKENS = 400
# Rough projected input size — actual is metered by the API.
_PROJECTED_INPUT_TOKENS = 4_000


@dataclass(frozen=True)
class Citation:
    """One supporting passage. Shape mirrors the frontend Citation type so
    the API can pass these through with `model_dump()` and no remapping."""
    chunk_id: int
    doc_id: str
    item: str
    section_title: str
    body_start: int
    body_end: int
    quote: str


@dataclass(frozen=True)
class CellResult:
    """The shape every cell in the matrix renders to. Mirrors the
    frontend CellResult so we can serialize 1:1."""
    doc_id: str
    question_id: str
    status: Literal["done", "error"]
    answer: str | None
    citations: list[Citation]
    cost_usd: float
    latency_ms: int
    error: str | None = None


_SYSTEM_PROMPT = """You are a careful financial analyst answering questions about a single SEC filing.

You will receive a question and numbered passages extracted from that filing. Each passage starts with [N] where N is the passage's chunk_id.

Rules:
1. Answer using ONLY information present in the passages. Do not bring in outside knowledge or make assumptions.
2. If the passages do not contain enough information to answer, respond with "The provided context does not contain enough information to answer."
3. Be concise (1-3 sentences). Quote specific numbers, dates, and segment names when present.
4. List the chunk_ids of every passage you actually used in your answer.

Return a JSON object with exactly this shape:
{
  "answer": "your one-to-three sentence answer here",
  "cited_chunk_ids": [<int>, <int>, ...]
}
"""


class CellAgent:
    """Stateless cell evaluator. Construct once per process; call answer_cell."""

    def __init__(
        self,
        client: OpenAI | None = None,
        embedder: EmbeddingClient | None = None,
    ) -> None:
        s = get_settings()
        self._client = client or OpenAI(api_key=s.openai_api_key)
        self._model = s.llm_model
        self._budget = s.daily_budget_usd
        self._embedder = embedder  # may be None; hybrid_search makes its own

    def answer_cell(
        self,
        doc_id: str,
        question: str,
        question_id: str = "ad-hoc",
        k: int = 5,
    ) -> CellResult:
        """Run the full cell pipeline. Always returns a CellResult, never raises
        (except BudgetExceeded — let that propagate so the matrix engine
        can stop fan-out instead of writing 50 red cells).
        """
        t0 = time.perf_counter()

        try:
            hits = hybrid_search(
                question,
                doc_ids=[doc_id],
                k=k,
                embedder=self._embedder,
            )
        except Exception as e:
            return self._error_result(doc_id, question_id, t0, f"retrieval failed: {e}")

        if not hits:
            return self._error_result(doc_id, question_id, t0, "no retrieval hits")

        messages = self._build_messages(question, hits)
        try:
            answer_text, cited_ids, cost = self._complete(messages)
        except Exception as e:
            return self._error_result(doc_id, question_id, t0, f"completion failed: {e}")

        citations = self._resolve_citations(hits, cited_ids)
        latency = int((time.perf_counter() - t0) * 1000)

        log.info(
            "cell.done",
            doc_id=doc_id,
            question_id=question_id,
            answer_chars=len(answer_text),
            citations=len(citations),
            cost_usd=round(cost, 6),
            latency_ms=latency,
        )
        return CellResult(
            doc_id=doc_id,
            question_id=question_id,
            status="done",
            answer=answer_text,
            citations=citations,
            cost_usd=cost,
            latency_ms=latency,
        )

    # ---- internals ----------------------------------------------------

    def _build_messages(self, question: str, hits: list[Hit]) -> list[dict]:
        passages = "\n\n".join(
            f"[{h.chunk_id}] (Item {h.item} — {h.section_title})\n{h.text}"
            for h in hits
        )
        user = f"Question: {question}\n\nPassages:\n{passages}"
        return [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ]

    def _complete(self, messages: list[dict]) -> tuple[str, list[int], float]:
        """Make the chat-completion call. Returns (answer, cited_ids, cost_usd)."""
        request_id = uuid.uuid4().hex
        projected_cost = self._cost_for_tokens(_PROJECTED_INPUT_TOKENS, _MAX_OUTPUT_TOKENS)
        guard_budget(projected_cost, self._budget)

        t0 = time.perf_counter()
        resp = self._call_openai(messages)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        usage = resp.usage
        in_tokens = usage.prompt_tokens
        out_tokens = usage.completion_tokens
        cost = self._cost_for_tokens(in_tokens, out_tokens)

        log_llm_usage(
            request_id=request_id,
            operation="completion",
            model=self._model,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
        )
        log.info(
            "completion.call",
            request_id=request_id,
            model=self._model,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_usd=round(cost, 6),
            latency_ms=latency_ms,
        )

        raw = resp.choices[0].message.content or ""
        answer, cited_ids = _parse_response(raw)
        return answer, cited_ids, cost

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def _call_openai(self, messages: list[dict]):
        return self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=_MAX_OUTPUT_TOKENS,
            temperature=0.0,
        )

    def _cost_for_tokens(self, input_tokens: int, output_tokens: int) -> float:
        prices = COMPLETION_PRICING_USD_PER_1M.get(self._model)
        if prices is None:
            raise KeyError(
                f"No price entry for completion model {self._model!r}. "
                f"Add it to COMPLETION_PRICING_USD_PER_1M."
            )
        in_price, out_price = prices
        return (input_tokens * in_price + output_tokens * out_price) / 1_000_000

    def _resolve_citations(self, hits: list[Hit], cited_ids: list[int]) -> list[Citation]:
        """Map cited chunk_ids back to Citation objects.

        The LLM might cite ids it wasn't given (rare, but happens) — drop
        those silently rather than fabricating quotes. Order follows the
        LLM's citation order so the UI shows the most-important first.
        """
        hits_by_id = {h.chunk_id: h for h in hits}
        out: list[Citation] = []
        for cid in cited_ids:
            h = hits_by_id.get(cid)
            if h is None:
                continue
            out.append(
                Citation(
                    chunk_id=h.chunk_id,
                    doc_id=h.doc_id,
                    item=h.item,
                    section_title=h.section_title,
                    body_start=h.body_start,
                    body_end=h.body_end,
                    quote=h.text,
                )
            )
        return out

    def _error_result(
        self, doc_id: str, question_id: str, t0: float, error: str
    ) -> CellResult:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        log.warning(
            "cell.error",
            doc_id=doc_id,
            question_id=question_id,
            error=error,
            latency_ms=latency_ms,
        )
        return CellResult(
            doc_id=doc_id,
            question_id=question_id,
            status="error",
            answer=None,
            citations=[],
            cost_usd=0.0,
            latency_ms=latency_ms,
            error=error,
        )


def _parse_response(raw: str) -> tuple[str, list[int]]:
    """Parse the LLM's JSON envelope. Raises ValueError on malformed output."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned non-JSON: {raw[:200]!r}") from e

    answer = data.get("answer")
    cited = data.get("cited_chunk_ids", [])
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError(f"LLM response missing 'answer' string: {data!r}")
    if not isinstance(cited, list) or not all(isinstance(x, int) for x in cited):
        raise ValueError(f"LLM 'cited_chunk_ids' must be list[int]: {cited!r}")
    return answer.strip(), cited
