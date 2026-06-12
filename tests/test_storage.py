"""Storage smoke tests.

We don't have a live Postgres in CI, so these verify:
  - ORM models declare the columns we expect.
  - FilingMeta builds cleanly from realistic EDGAR-shaped data.
  - The DDL SQLAlchemy emits names the indexes / vector column correctly.

Integration tests against a real DB live behind `@pytest.mark.integration`
and run only when DATABASE_URL points somewhere reachable.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.schema import CreateTable

from src.core.config import get_settings
from src.storage.repository import FilingMeta, _estimate_tokens
from src.storage.schema import Base, ChunkRow, DocumentRow


def test_document_row_has_expected_columns():
    cols = {c.name for c in DocumentRow.__table__.columns}
    assert cols == {
        "doc_id", "ticker", "cik", "form",
        "filing_date", "primary_doc", "ingested_at",
    }
    assert DocumentRow.__table__.primary_key.columns.keys() == ["doc_id"]


def test_chunk_row_has_expected_columns():
    cols = {c.name for c in ChunkRow.__table__.columns}
    assert cols == {
        "id", "doc_id", "item", "section_title", "chunk_index",
        "text", "body_start", "body_end", "token_count",
        "embedding", "created_at",
    }


def test_chunk_embedding_dimension_matches_settings():
    embedding_col = ChunkRow.__table__.columns["embedding"]
    # pgvector.sqlalchemy.Vector stores its dim on the type instance.
    assert embedding_col.type.dim == get_settings().embedding_dim


def test_chunks_table_has_composite_lookup_index():
    index_names = {ix.name for ix in ChunkRow.__table__.indexes}
    assert "ix_chunks_doc_item_idx" in index_names


def test_chunks_doc_id_cascades():
    fk = next(iter(ChunkRow.__table__.columns["doc_id"].foreign_keys))
    assert fk.ondelete == "CASCADE"


def test_create_table_ddl_emits_vector_column():
    from sqlalchemy.dialects import postgresql

    ddl = str(CreateTable(ChunkRow.__table__).compile(dialect=postgresql.dialect()))
    # The vector(N) column type makes it into the DDL — proves pgvector
    # type registration is wired up correctly.
    assert "VECTOR(" in ddl.upper()


def test_filing_meta_round_trips():
    meta = FilingMeta(
        doc_id="0000320193-24-000123",
        ticker="AAPL",
        cik="0000320193",
        form="10-K",
        filing_date=date(2024, 11, 1),
        primary_doc="aapl-20240928.htm",
    )
    assert meta.doc_id == "0000320193-24-000123"
    assert meta.form == "10-K"


def test_estimate_tokens_uses_four_chars_per_token():
    assert _estimate_tokens("") == 1  # never zero — avoids divide-by-zero downstream
    assert _estimate_tokens("a" * 40) == 10
    assert _estimate_tokens("a" * 41) == 10  # integer division


def test_base_registry_contains_both_tables():
    table_names = set(Base.metadata.tables.keys())
    assert {"documents", "chunks"}.issubset(table_names)
