"""FastAPI entrypoint.

Endpoints:
  GET  /health           liveness
  GET  /api/filings      list ingested filings (rows of the matrix)
  POST /api/matrix       run the grid: returns CellOut[] when all cells finish
  POST /api/matrix/stream same grid as SSE; one `data: {...}\\n\\n` per cell

CORS is opened wide for the demo. Tighten before any deployment.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from src.api.models import CellOut, CitationOut, FilingOut, MatrixRequest
from src.core.config import get_settings
from src.core.logging import configure_logging, get_logger
from src.matrix import Question, run_matrix
from src.storage.db import get_session
from src.storage.schema import DocumentRow

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    log.info("startup", llm_model=settings.llm_model)
    yield
    log.info("shutdown")


app = FastAPI(title="Finance Matrix Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/filings", response_model=list[FilingOut])
async def list_filings() -> list[FilingOut]:
    """Return every ingested filing, newest first.

    Powers the row picker in the frontend. No pagination yet — at ~1 row
    per filing this is fine well into thousands; revisit when needed.
    """
    with get_session() as session:
        rows = session.execute(
            select(DocumentRow).order_by(DocumentRow.filing_date.desc())
        ).scalars()
        return [
            FilingOut(
                doc_id=r.doc_id,
                ticker=r.ticker,
                form=r.form,
                filing_date=r.filing_date,
            )
            for r in rows
        ]


@app.post("/api/matrix", response_model=list[CellOut])
async def post_matrix(req: MatrixRequest) -> list[CellOut]:
    """Run every (doc, question) cell and return all results once complete.

    For long-running grids prefer /api/matrix/stream — this endpoint blocks
    until the last cell finishes.
    """
    questions = [Question(id=q.id, text=q.text) for q in req.questions]
    url_for = _resolve_source_urls(req.doc_ids)
    cells: list[CellOut] = []
    async for cell in run_matrix(req.doc_ids, questions, k=req.k):
        cells.append(_to_out(cell, url_for))
    return cells


@app.post("/api/matrix/stream")
async def post_matrix_stream(req: MatrixRequest) -> StreamingResponse:
    """Server-Sent Events: one cell per `data: {...}\\n\\n` line.

    The frontend opens an EventSource and renders each cell as it arrives —
    no waiting for the slowest cell.
    """
    questions = [Question(id=q.id, text=q.text) for q in req.questions]
    url_for = _resolve_source_urls(req.doc_ids)

    async def event_stream():
        async for cell in run_matrix(req.doc_ids, questions, k=req.k):
            payload = _to_out(cell, url_for).model_dump_json()
            yield f"data: {payload}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _to_out(cell, url_for: dict[str, str | None]) -> CellOut:
    """CellResult dataclass → CellOut pydantic. Shapes match 1:1.

    `url_for` is a doc_id → EDGAR URL map prepared by the caller so we
    don't hit Postgres once per citation.
    """
    return CellOut(
        doc_id=cell.doc_id,
        question_id=cell.question_id,
        status=cell.status,
        answer=cell.answer,
        citations=[
            CitationOut(
                chunk_id=c.chunk_id,
                doc_id=c.doc_id,
                item=c.item,
                section_title=c.section_title,
                body_start=c.body_start,
                body_end=c.body_end,
                quote=c.quote,
                source_url=url_for.get(c.doc_id),
            )
            for c in cell.citations
        ],
        cost_usd=cell.cost_usd,
        latency_ms=cell.latency_ms,
        error=cell.error,
    )


def _resolve_source_urls(doc_ids: list[str]) -> dict[str, str | None]:
    """Return {doc_id: EDGAR URL} for every doc_id (None if unknown).

    EDGAR archive convention:
        https://www.sec.gov/Archives/edgar/data/<cik_int>/<accession_nodash>/<primary_doc>
    """
    if not doc_ids:
        return {}
    with get_session() as session:
        rows = session.execute(
            select(DocumentRow).where(DocumentRow.doc_id.in_(doc_ids))
        ).scalars()
        urls: dict[str, str | None] = {d: None for d in doc_ids}
        for r in rows:
            acc_nodash = r.doc_id.replace("-", "")
            urls[r.doc_id] = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{int(r.cik)}/{acc_nodash}/{r.primary_doc}"
            )
        return urls
