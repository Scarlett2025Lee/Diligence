"""CLI: python -m scripts.embed [--limit N]

Backfills embeddings for every chunk where embedding IS NULL. Respects the
DAILY_BUDGET_USD guard — if the projected cost of the next batch would push
us over budget, the run raises and you get a partial backfill (safe; re-run
tomorrow or raise the budget in .env).
"""
from __future__ import annotations

import argparse

from src.core.logging import configure_logging, get_logger
from src.embeddings.backfill import backfill_embeddings

log = get_logger(__name__)


def main(limit: int | None) -> None:
    configure_logging()
    stats = backfill_embeddings(limit=limit)
    print(
        f"embedded {stats.chunks_embedded} chunks across {stats.batches} batches | "
        f"{stats.total_tokens:,} tokens | ${stats.total_cost_usd:.4f}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after this many chunks. Default: embed everything pending.",
    )
    args = parser.parse_args()
    main(args.limit)
