"""Matrix engine: rows (documents) x columns (questions) -> grid of cited cells.

Phase 2 core. Responsibilities:
  - fan out N*M cell jobs with bounded concurrency (asyncio.Semaphore)
  - per-cell cost/latency accounting, budget kill-switch
  - partial results: a grid with 3 failed cells is still useful
"""
