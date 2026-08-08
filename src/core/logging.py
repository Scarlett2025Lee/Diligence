"""Structured logging — the Day-2 checklist starts here.

Every LLM call should log: model, tokens_in, tokens_out, latency_ms,
estimated_cost_usd, and a request_id. No logs = no evals = no iteration.
"""
import structlog


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ]
    )


def get_logger(name: str):
    return structlog.get_logger(name)
