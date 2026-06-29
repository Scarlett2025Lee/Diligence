"""Pydantic shapes for the HTTP boundary.

These mirror frontend/lib/types.ts exactly — when one side changes, the
other must change in the same commit. The matching is enforced by
manual review and the integration test that hits the live API.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class FilingOut(BaseModel):
    doc_id: str
    ticker: str | None
    form: str
    filing_date: date


class QuestionIn(BaseModel):
    id: str
    text: str


class CitationOut(BaseModel):
    chunk_id: int
    doc_id: str
    item: str
    section_title: str
    body_start: int
    body_end: int
    quote: str


class CellOut(BaseModel):
    doc_id: str
    question_id: str
    status: Literal["pending", "running", "done", "error"]
    answer: str | None
    citations: list[CitationOut]
    cost_usd: float
    latency_ms: int
    error: str | None = None


class MatrixRequest(BaseModel):
    doc_ids: list[str] = Field(min_length=1)
    questions: list[QuestionIn] = Field(min_length=1)
    k: int = Field(default=5, ge=1, le=20)
