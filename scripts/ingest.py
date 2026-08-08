"""CLI: python -m scripts.ingest --tickers AAPL MSFT --forms 10-K [--limit 1]

End-to-end ingestion for one or more tickers:

    ticker -> CIK -> recent filings -> primary HTML -> sections -> chunks -> Postgres

Embeddings are NOT computed here yet — chunks land with embedding=NULL and
a follow-up step backfills them. This keeps the slow + paid step decoupled
from parsing, and makes chunker iteration cheap.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date

from src.ingestion.chunking import chunk_section
from src.ingestion.edgar import EdgarClient
from src.ingestion.sections import parse_sections
from src.storage import init_schema
from src.storage.repository import FilingMeta, save_filing


async def ingest_ticker(
    client: EdgarClient,
    ticker: str,
    forms: tuple[str, ...],
    limit: int,
) -> None:
    cik = await client.cik_for_ticker(ticker)
    filings = await client.recent_filings(cik, forms=forms)
    if not filings:
        print(f"{ticker}: no {'/'.join(forms)} filings found")
        return

    for filing in filings[:limit]:
        html = await client.fetch_filing_html(filing)
        # Form matters: 10-Qs get part-scoped item ids ("I.2"), 10-Ks flat.
        sections = parse_sections(html, form=filing["form"])
        chunks = []
        for section in sections:
            chunks.extend(chunk_section(section, doc_id=filing["accession"]))

        meta = FilingMeta(
            doc_id=filing["accession"],
            ticker=ticker.upper(),
            cik=cik,
            form=filing["form"],
            filing_date=date.fromisoformat(filing["filing_date"]),
            primary_doc=filing["primary_doc"],
        )
        n = save_filing(meta, chunks)
        print(
            f"{ticker} {filing['form']} {filing['filing_date']} "
            f"({filing['accession']}): {len(sections)} sections, {n} chunks"
        )


async def main(tickers: list[str], forms: list[str], limit: int) -> None:
    init_schema()
    client = EdgarClient()
    for ticker in tickers:
        await ingest_ticker(client, ticker, tuple(forms), limit)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", nargs="+", required=True)
    parser.add_argument("--forms", nargs="+", default=["10-K"])
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Most recent N filings per ticker per form",
    )
    args = parser.parse_args()
    asyncio.run(main(args.tickers, args.forms, args.limit))
