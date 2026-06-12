"""Persistence layer.

Postgres + pgvector is the single store for chunk text AND dense vectors —
one connection, one transaction, fewer moving parts than a sidecar vector DB.

Public surface:
    from src.storage import init_schema, save_filing, get_chunks_for_doc
"""
from src.storage.db import get_engine, get_session, init_schema
from src.storage.repository import (
    fetch_document,
    get_chunks_for_doc,
    save_filing,
)
from src.storage.schema import Base, ChunkRow, DocumentRow

__all__ = [
    "Base",
    "ChunkRow",
    "DocumentRow",
    "fetch_document",
    "get_chunks_for_doc",
    "get_engine",
    "get_session",
    "init_schema",
    "save_filing",
]
