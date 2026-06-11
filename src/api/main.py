"""FastAPI entrypoint.

Endpoints (planned):
  GET  /health            - liveness
  POST /documents/ingest  - pull filings/transcripts for tickers
  POST /ask               - single-cell QA (phase 1)
  POST /matrix            - full grid run (phase 2)
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.config import get_settings
from src.core.logging import configure_logging, get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    log.info("startup", llm_model=settings.llm_model)
    yield
    log.info("shutdown")


app = FastAPI(title="Finance Matrix Agent", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
