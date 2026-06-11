# Finance Matrix Agent

A Hebbia-style document intelligence system for financial filings and earnings calls.
Ask structured questions across many companies at once — get a **grid of cited answers**,
not a chat transcript.

> *Documents are rows. Questions are columns. Every cell is an agent's answer with citations.*

## Why this exists

Chat is a bottleneck for serious financial research. Analysts don't want one answer —
they want the same 8 questions answered across 40 companies' 10-Ks, with sources they
can defend. This project rebuilds the core ideas behind Hebbia's Matrix:

- **Grid, not chat** — batch question-answering over a document set
- **Query decomposition** — complex questions broken into retrievable sub-steps
- **Hybrid retrieval** — BM25 + dense vectors + reranking over SEC filings & call transcripts
- **Citation-first** — every cell traces back to exact passages (page/section anchors)
- **Evals as a feature** — a benchmark set with measured accuracy, not vibes

## Data corpus

| Source | What | How |
|---|---|---|
| SEC EDGAR | 10-K / 10-Q filings | Official EDGAR submissions + full-text APIs (free, rate-limited, requires User-Agent) |
| Earnings calls | Quarterly call transcripts | Pluggable provider (`src/ingestion/transcripts.py`) — FMP / API Ninjas / manual drop-in |

## Architecture

```
                       ┌─────────────────────────────┐
                       │      FastAPI  (src/api)      │
                       │  /matrix  /documents  /ask   │
                       └──────────────┬──────────────┘
                                      │
                      ┌───────────────▼───────────────┐
                      │     Matrix Engine (src/matrix) │
                      │  rows × cols → cell jobs       │
                      └───────┬───────────────┬───────┘
                              │               │
                ┌─────────────▼───┐   ┌───────▼─────────────┐
                │ Agents           │   │ Retrieval            │
                │ decompose/route/ │   │ BM25 + pgvector +    │
                │ extract/cite     │   │ reranker (hybrid)    │
                └─────────────┬───┘   └───────┬─────────────┘
                              │               │
                      ┌───────▼───────────────▼───────┐
                      │  Postgres + pgvector           │
                      │  chunks, embeddings, metadata  │
                      └───────────────▲───────────────┘
                                      │
                       ┌──────────────┴──────────────┐
                       │   Ingestion (src/ingestion)  │
                       │   EDGAR + transcripts →      │
                       │   parse → chunk → embed      │
                       └─────────────────────────────┘
```

## Quickstart

```bash
cp .env.example .env          # add your API keys
docker compose up -d          # Postgres + pgvector
make install                  # python deps
make ingest TICKERS="AAPL MSFT" FORMS="10-K"
make serve                    # FastAPI on :8000
```

## Roadmap

- [x] Repo scaffold, Docker, config
- [ ] **Phase 1 — Pipeline**: EDGAR ingestion → chunking → hybrid index
- [ ] **Phase 1 — Single-cell QA**: one question, one document, with citations
- [ ] **Phase 2 — Matrix engine**: N docs × M questions, parallel cell jobs
- [ ] **Phase 2 — Eval harness**: 50–100 labeled Q/A pairs, accuracy table in this README
- [ ] **Phase 2 — Observability**: structured logs, cost-per-cell, latency metrics
- [ ] **Phase 3 — One differentiator**: transcript sentiment column / fine-tuned extractor / multi-tenant

## Production checklist (Day-2)

Structured logging · eval set · model fallback chain · cost alarms.
No logs = no evals = no iteration.

## License

MIT
