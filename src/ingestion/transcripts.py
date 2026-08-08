"""Earnings call transcript ingestion — pluggable providers.

Transcripts have no free official source like EDGAR, so this module defines a
provider interface with three implementations:

  - ManualProvider: drop .txt/.json files into data/raw/transcripts/ (zero cost, demo-safe)
  - FMPProvider: Financial Modeling Prep API (free tier available)
  - ApiNinjasProvider: API Ninjas earnings transcripts endpoint

Keep the interface identical so retrieval downstream never knows the difference.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class Transcript(dict):
    """Keys: ticker, quarter, year, date, text"""


class TranscriptProvider(Protocol):
    async def fetch(self, ticker: str, year: int, quarter: int) -> Transcript | None: ...


class ManualProvider:
    """Reads transcripts from data/raw/transcripts/{TICKER}_{YEAR}Q{Q}.txt"""

    def __init__(self, root: Path = Path("data/raw/transcripts")) -> None:
        self.root = root

    async def fetch(self, ticker: str, year: int, quarter: int) -> Transcript | None:
        path = self.root / f"{ticker.upper()}_{year}Q{quarter}.txt"
        if not path.exists():
            return None
        return Transcript(
            ticker=ticker.upper(), year=year, quarter=quarter, date=None, text=path.read_text()
        )


# TODO(phase-1): FMPProvider / ApiNinjasProvider using settings.transcripts_api_key
