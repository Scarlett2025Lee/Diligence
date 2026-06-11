"""SEC EDGAR client.

Free, official, rate-limited (max 10 req/s; SEC asks for a real User-Agent).
Docs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces

Flow:
    ticker -> CIK -> submissions index -> filing documents (10-K / 10-Q) -> raw HTML
"""
from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import get_settings

EDGAR_BASE = "https://www.sec.gov"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:0>10}.json"
TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"


class EdgarClient:
    def __init__(self) -> None:
        self._headers = {"User-Agent": get_settings().edgar_user_agent}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def _get(self, url: str) -> httpx.Response:
        async with httpx.AsyncClient(headers=self._headers, timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp

    async def cik_for_ticker(self, ticker: str) -> str:
        """Resolve a ticker symbol to a zero-padded CIK string."""
        resp = await self._get(TICKER_MAP_URL)
        data = resp.json()
        for entry in data.values():
            if entry["ticker"].upper() == ticker.upper():
                return f"{entry['cik_str']:0>10}"
        raise ValueError(f"Ticker not found on EDGAR: {ticker}")

    async def recent_filings(self, cik: str, forms: tuple[str, ...] = ("10-K", "10-Q")) -> list[dict]:
        """Return recent filings of the given form types with accession metadata."""
        resp = await self._get(SUBMISSIONS_URL.format(cik=cik))
        recent = resp.json()["filings"]["recent"]
        filings = []
        for i, form in enumerate(recent["form"]):
            if form in forms:
                filings.append(
                    {
                        "form": form,
                        "accession": recent["accessionNumber"][i],
                        "filing_date": recent["filingDate"][i],
                        "primary_doc": recent["primaryDocument"][i],
                        "cik": cik,
                    }
                )
        return filings

    async def fetch_filing_html(self, filing: dict) -> str:
        """Download the primary document HTML for a filing."""
        acc_nodash = filing["accession"].replace("-", "")
        url = (
            f"{EDGAR_BASE}/Archives/edgar/data/"
            f"{int(filing['cik'])}/{acc_nodash}/{filing['primary_doc']}"
        )
        resp = await self._get(url)
        return resp.text
