"""Matrix engine — fan out N docs × M questions into cited cells."""
from src.matrix.engine import (
    DEFAULT_MAX_CONCURRENCY,
    Question,
    run_matrix,
)

__all__ = ["DEFAULT_MAX_CONCURRENCY", "Question", "run_matrix"]
