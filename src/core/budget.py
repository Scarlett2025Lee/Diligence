"""Daily-budget bookkeeping shared by every LLM caller.

The single source of truth for "how much have we spent today" — both the
embedding client and the cell agent read and write through here, so a
single `DAILY_BUDGET_USD` cap covers all LLM operations.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, select

from src.storage.db import get_session
from src.storage.schema import LlmUsageRow


class BudgetExceeded(RuntimeError):
    """Raised when a call would push today's spend past DAILY_BUDGET_USD."""


def spent_today() -> float:
    """Total USD spent on LLM calls since 00:00 today (server local time)."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    with get_session() as session:
        result = session.execute(
            select(func.coalesce(func.sum(LlmUsageRow.cost_usd), 0.0)).where(
                LlmUsageRow.created_at >= today_start
            )
        ).scalar_one()
        return float(result)


def guard_budget(projected_cost: float, daily_budget_usd: float) -> None:
    """Raise BudgetExceeded if `projected_cost` would push us over budget."""
    spent = spent_today()
    if spent + projected_cost > daily_budget_usd:
        raise BudgetExceeded(
            f"Daily budget ${daily_budget_usd:.2f} would be exceeded: "
            f"spent ${spent:.4f}, this call adds ${projected_cost:.4f}"
        )


def log_llm_usage(
    *,
    request_id: str,
    operation: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    latency_ms: int,
) -> None:
    """Insert one row into llm_usage. Source of truth for cost dashboards."""
    with get_session() as session:
        session.add(
            LlmUsageRow(
                request_id=request_id,
                operation=operation,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
            )
        )
