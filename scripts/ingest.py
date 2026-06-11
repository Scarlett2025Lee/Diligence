"""CLI: python -m scripts.ingest --tickers AAPL MSFT --forms 10-K"""
import argparse
import asyncio

from src.ingestion.edgar import EdgarClient


async def main(tickers: list[str], forms: list[str]) -> None:
    client = EdgarClient()
    for ticker in tickers:
        cik = await client.cik_for_ticker(ticker)
        filings = await client.recent_filings(cik, forms=tuple(forms))
        print(f"{ticker}: {len(filings)} filings found (latest: {filings[0]['filing_date'] if filings else 'n/a'})")
        # TODO(phase-1): fetch_filing_html -> parse -> chunk -> embed -> store


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", nargs="+", required=True)
    parser.add_argument("--forms", nargs="+", default=["10-K"])
    args = parser.parse_args()
    asyncio.run(main(args.tickers, args.forms))
