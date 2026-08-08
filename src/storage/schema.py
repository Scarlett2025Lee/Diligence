"""SQLAlchemy 2.0 ORM models for filings and chunks.

Two tables, one vector column:

  documents — one row per SEC filing. doc_id is the accession number
              (globally unique on EDGAR), which gives us natural idempotency
              on re-ingestion.

  chunks    — one row per chunk emitted by `chunk_section`. The embedding
              column is nullable so we can persist text now and backfill
              vectors when the embedding client lands. Citation anchors
              (item + body_start/body_end) live here, not on documents,
              because citations point at chunks not whole filings.

Indexes:
  - chunks(doc_id, item, chunk_index) for fast per-filing lookups.
  - ivfflat on embedding for ANN search once vectors are populated. We
    create this lazily in `init_schema` since the empty-table case can't
    pick good IVF parameters.
"""
from __future__ import annotations

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.core.config import get_settings


class Base(DeclarativeBase):
    pass


class DocumentRow(Base):
    __tablename__ = "documents"

    doc_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ticker: Mapped[str | None] = mapped_column(String(16), index=True)
    cik: Mapped[str] = mapped_column(String(10), index=True)
    form: Mapped[str] = mapped_column(String(16))  # "10-K", "10-Q"
    filing_date: Mapped[date] = mapped_column(Date)
    primary_doc: Mapped[str] = mapped_column(String(256))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    chunks: Mapped[list["ChunkRow"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class LlmUsageRow(Base):
    """One row per LLM call (embedding or completion).

    Powers the daily-budget guard and the per-cell cost telemetry the eval
    harness will key off. Every call writes here — there is no "free" LLM
    call in this codebase by design.
    """
    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    operation: Mapped[str] = mapped_column(String(16))  # "embedding" | "completion"
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float)
    latency_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class ChunkRow(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("documents.doc_id", ondelete="CASCADE"),
        index=True,
    )
    item: Mapped[str] = mapped_column(String(8))
    section_title: Mapped[str] = mapped_column(String(256))
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    body_start: Mapped[int] = mapped_column(Integer)
    body_end: Mapped[int] = mapped_column(Integer)
    token_count: Mapped[int] = mapped_column(Integer)

    # Nullable so ingest can persist text first and embed in a second pass.
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(get_settings().embedding_dim), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    document: Mapped[DocumentRow] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_doc_item_idx", "doc_id", "item", "chunk_index"),
    )
