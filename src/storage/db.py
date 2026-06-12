"""Engine, session, and schema bootstrap.

We use a single module-level Engine — psycopg pools connections internally,
and the matrix engine fans out cell jobs as asyncio tasks so connection
churn matters. A get_session() context manager keeps transactions tidy.

`init_schema` is idempotent: safe to run on every container start. It
creates the pgvector extension (a no-op if already present) and then runs
SQLAlchemy's create_all. We deliberately do NOT create the ivfflat index
here — IVF wants a populated table to choose good `lists`. A separate
helper builds it after the first bulk embed.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import get_settings
from src.storage.schema import Base


@lru_cache
def get_engine() -> Engine:
    """Module-level engine; one per process."""
    return create_engine(get_settings().database_url, pool_pre_ping=True, future=True)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


@contextmanager
def get_session() -> Iterator[Session]:
    """Transactional session context. Commits on clean exit, rolls back on error."""
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_schema(engine: Engine | None = None) -> None:
    """Create the pgvector extension and ORM tables. Idempotent."""
    engine = engine or get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)


def create_vector_index(engine: Engine | None = None, lists: int = 100) -> None:
    """Build the IVFFlat index over `chunks.embedding`.

    Call this AFTER the first sizeable batch of embeddings has been written.
    Rule of thumb: lists ~= sqrt(rows). 100 is fine for tens of thousands
    of chunks; revisit if the corpus grows past ~1M.
    """
    engine = engine or get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_ivfflat "
                "ON chunks USING ivfflat (embedding vector_cosine_ops) "
                f"WITH (lists = {int(lists)})"
            )
        )
