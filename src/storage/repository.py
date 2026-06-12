"""Read/write helpers above the ORM.

Keep callers (ingest script, retrieval, /ask endpoint) out of SQLAlchemy
internals — they should think in terms of `Chunk` + filing metadata, not
sessions and merge() semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import delete, select

from src.ingestion.chunking import Chunk
from src.storage.db import get_session
from src.storage.schema import ChunkRow, DocumentRow


@dataclass(frozen=True)
class FilingMeta:
    """Everything we know about a filing before chunking it."""
    doc_id: str          # accession number, e.g. "0000320193-24-000123"
    ticker: str | None
    cik: str
    form: str            # "10-K" or "10-Q"
    filing_date: date
    primary_doc: str     # filename of the primary HTML doc


def save_filing(meta: FilingMeta, chunks: list[Chunk]) -> int:
    """Persist a filing and its chunks. Idempotent on doc_id.

    Re-ingesting the same accession number replaces the prior chunks —
    that's the right call because chunker tweaks should flow through to
    storage without manual cleanup.

    Returns the number of chunk rows written.
    """
    with get_session() as session:
        existing = session.get(DocumentRow, meta.doc_id)
        if existing is None:
            session.add(
                DocumentRow(
                    doc_id=meta.doc_id,
                    ticker=meta.ticker,
                    cik=meta.cik,
                    form=meta.form,
                    filing_date=meta.filing_date,
                    primary_doc=meta.primary_doc,
                )
            )
        else:
            # Update mutable metadata in case it changed (rare — accession
            # is stable — but cheap insurance).
            existing.ticker = meta.ticker
            existing.cik = meta.cik
            existing.form = meta.form
            existing.filing_date = meta.filing_date
            existing.primary_doc = meta.primary_doc
            session.execute(delete(ChunkRow).where(ChunkRow.doc_id == meta.doc_id))

        rows = [
            ChunkRow(
                doc_id=meta.doc_id,
                item=c.item,
                section_title=c.section_title,
                chunk_index=c.chunk_index,
                text=c.text,
                body_start=c.body_start,
                body_end=c.body_end,
                token_count=_estimate_tokens(c.text),
                embedding=None,
            )
            for c in chunks
        ]
        session.add_all(rows)
        return len(rows)


def fetch_document(doc_id: str) -> DocumentRow | None:
    with get_session() as session:
        return session.get(DocumentRow, doc_id)


def get_chunks_for_doc(doc_id: str) -> list[ChunkRow]:
    """Return chunks for one filing in stable (item, chunk_index) order."""
    with get_session() as session:
        stmt = (
            select(ChunkRow)
            .where(ChunkRow.doc_id == doc_id)
            .order_by(ChunkRow.item, ChunkRow.chunk_index)
        )
        return list(session.execute(stmt).scalars())


def _estimate_tokens(text: str) -> int:
    """4 chars/token approximation. Replaced by tiktoken once embeddings land."""
    return max(1, len(text) // 4)
