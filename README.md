# Finance Matrix Agent

A Hebbia-style financial research prototype that answers the same questions across SEC filings in a matrix of source-linked answers. Documents form the rows; questions form the columns.

## What is implemented

- SEC EDGAR ingestion, section parsing, chunking, and embedding scripts.
- PostgreSQL/pgvector storage, BM25 and dense retrieval, and reciprocal rank fusion.
- A cell agent that retrieves passages from one filing, requests a structured LLM answer, and resolves citations to retrieved chunks.
- A matrix engine with bounded concurrency and a FastAPI API with streamed cell results.
- A Next.js frontend with matrix and citation components.
- A retrieval evaluation harness, labeled queries, and recorded results in [eval/README.md](eval/README.md).

This is a portfolio prototype, not a production service. Citation links expose supporting passages; they do not independently prove that every generated claim is correct.

## Architecture

SEC filings → section parsing and chunks → embeddings and PostgreSQL/pgvector → retrieval → cell answers and citations → matrix API → Next.js interface.

The implemented hybrid retriever combines BM25 and dense rankings using reciprocal rank fusion. It does not implement a separate learned reranker.

## Retrieval evaluation

The recorded benchmark uses 20 filings from 10 companies, 2,853 chunks, and 40 labeled questions.

| Retrieval mode | Recall@5 | Recall@10 | MRR |
|---|---:|---:|---:|
| BM25 | 0.15 | 0.33 | 0.07 |
| Dense | 0.45 | 0.57 | 0.27 |
| Hybrid | 0.35 | 0.53 | 0.21 |

Dense retrieval performed best overall in this whole-corpus experiment. Hybrid performed best on the semantic-query slice (Recall@10 0.46). These are previously recorded results, not a new validation run. The document-scoped setting used by the cell agent was not evaluated by that experiment.

See [the benchmark documentation](eval/README.md) for query categories, ground-truth construction, the IBM ingestion correction, and reproducibility constraints. The retrieval benchmark belongs to this project.

## Setup

Review `.env.example` and supply your own credentials and SEC User-Agent locally. Never commit `.env`.

```bash
cp .env.example .env
docker compose up -d
make install
make ingest TICKERS="AAPL MSFT" FORMS="10-K"
make serve
```

Embedding is a separate script in `scripts/embed.py`; inspect its CLI options before running it. Ingestion alone does not guarantee that vectors have been populated.

For the frontend, inspect [frontend/README.md](frontend/README.md) and `frontend/package.json`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | /health | Liveness |
| GET | /api/filings | List ingested filings |
| POST | /api/matrix | Return completed matrix cells |
| POST | /api/matrix/stream | Stream cells using server-sent events |

## Repository guide

- `src/ingestion/`: EDGAR access, sections, chunking, transcript adapter.
- `src/embeddings/`: embedding client and backfill.
- `src/retrieval/`: BM25, dense, and hybrid retrieval.
- `src/agents/`: cell answers and citation resolution.
- `src/matrix/`: concurrent cell execution.
- `src/api/`: HTTP endpoints and response models.
- `src/storage/`: database schema and repository helpers.
- `frontend/`: Next.js interface.
- `eval/`: retrieval test set, evaluation scripts, and recorded results.
- `tests/`: existing automated tests.

## Validation and limitations

```bash
make test
make lint
```

These commands are provided for local verification; they were not executed during this README update. Database-backed or live-model workflows require their configured services and credentials. The frozen database corpus is not included as a complete ready-to-run database snapshot.

The API currently allows broad CORS for demonstration. Authentication, deployment hardening, and comprehensive answer-quality evaluation remain further work. Stored model prices are historical configuration and require review before relying on cost estimates.
