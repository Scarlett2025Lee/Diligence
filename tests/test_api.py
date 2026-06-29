"""HTTP-boundary tests for the FastAPI app.

We don't exercise the live DB or OpenAI here — those are covered by
the unit tests in their respective modules. Here we check that the
HTTP contract matches what the frontend expects.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.agents import CellResult, Citation
from src.api.main import app


client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_filings_returns_rows_newest_first():
    fake_rows = [
        MagicMock(doc_id="d1", ticker="AAPL", form="10-K", filing_date=date(2024, 11, 1)),
        MagicMock(doc_id="d2", ticker="MSFT", form="10-K", filing_date=date(2024, 7, 30)),
    ]
    fake_session = MagicMock()
    fake_session.__enter__.return_value = fake_session
    fake_session.__exit__.return_value = False
    fake_session.execute.return_value.scalars.return_value = iter(fake_rows)

    with patch("src.api.main.get_session", return_value=fake_session):
        resp = client.get("/api/filings")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["doc_id"] == "d1"
    assert body[0]["ticker"] == "AAPL"
    assert body[0]["filing_date"] == "2024-11-01"


def test_post_matrix_returns_cell_results():
    async def fake_run_matrix(doc_ids, questions, *, k):
        for d in doc_ids:
            for q in questions:
                yield CellResult(
                    doc_id=d, question_id=q.id, status="done",
                    answer=f"answer for {d}/{q.id}",
                    citations=[
                        Citation(
                            chunk_id=42, doc_id=d, item="1A",
                            section_title="Risk Factors",
                            body_start=0, body_end=100,
                            quote="passage text",
                        )
                    ],
                    cost_usd=0.0003, latency_ms=2500,
                )

    payload = {
        "doc_ids": ["acc-1", "acc-2"],
        "questions": [{"id": "q1", "text": "What's revenue?"}],
        "k": 5,
    }

    with patch("src.api.main.run_matrix", fake_run_matrix):
        resp = client.post("/api/matrix", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    keys = {(c["doc_id"], c["question_id"]) for c in body}
    assert keys == {("acc-1", "q1"), ("acc-2", "q1")}
    cell = body[0]
    assert cell["status"] == "done"
    assert cell["answer"].startswith("answer for ")
    assert cell["citations"][0]["item"] == "1A"
    assert cell["citations"][0]["quote"] == "passage text"


def test_post_matrix_validates_min_inputs():
    # Empty doc_ids should 422 (Field min_length=1).
    resp = client.post(
        "/api/matrix",
        json={"doc_ids": [], "questions": [{"id": "q", "text": "?"}]},
    )
    assert resp.status_code == 422

    # Empty questions should 422 too.
    resp = client.post(
        "/api/matrix",
        json={"doc_ids": ["a"], "questions": []},
    )
    assert resp.status_code == 422


def test_post_matrix_stream_emits_sse_per_cell():
    async def fake_run_matrix(doc_ids, questions, *, k):
        for d in doc_ids:
            for q in questions:
                yield CellResult(
                    doc_id=d, question_id=q.id, status="done",
                    answer="x", citations=[], cost_usd=0.0, latency_ms=1,
                )

    payload = {
        "doc_ids": ["a", "b"],
        "questions": [{"id": "q", "text": "?"}],
    }
    with patch("src.api.main.run_matrix", fake_run_matrix):
        with client.stream("POST", "/api/matrix/stream", json=payload) as resp:
            assert resp.status_code == 200
            body = resp.read().decode()
    # Two cells -> two SSE frames.
    assert body.count("data: ") == 2
    assert "\"status\":\"done\"" in body
