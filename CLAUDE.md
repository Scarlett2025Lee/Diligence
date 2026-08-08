# CLAUDE.md — Finance Matrix Agent

## What this project is

A Hebbia-style document intelligence system: ask structured questions across many
financial documents at once and get a **grid of cited answers** (documents = rows,
questions = columns, each cell = one agent's answer with citations). Built by
**Wan Li** as the capstone for a 12-week AI engineering camp; the goal is a
resume-grade project demonstrating production LLM engineering, not a demo.

Inspiration: Hebbia's Matrix product. Key ideas we're reproducing:
- Grid interface instead of chat (humans supervise AI at scale)
- Query decomposition + multi-agent routing instead of one monolithic model call
- Citation-first answers (defensibility IS the product in finance)
- Hybrid retrieval tuned for financial text

## Data corpus (decided — don't relitigate)

- **SEC EDGAR 10-K / 10-Q filings** — official free API. User-Agent is required by
  SEC fair-access policy and is set in `.env` (`EDGAR_USER_AGENT`). Max 10 req/s.
- **Earnings call transcripts** — pluggable provider in `src/ingestion/transcripts.py`.
  Default is `ManualProvider` (drop `TICKER_YYYYQN.txt` files into
  `data/raw/transcripts/`) so demos cost nothing. FMP / API Ninjas providers are TODO.

## Architecture decisions (decided — don't relitigate)

- **No LangChain.** Vanilla `httpx` + Pydantic, per camp guidance: fewer abstraction
  layers, more transparent for learning and interviews.
- **Postgres + pgvector** for both chunk storage and dense vectors (one database,
  via docker-compose). BM25 via `rank-bm25` in-process for now.
- **Hybrid retrieval**: BM25 + dense, fused with Reciprocal Rank Fusion, then rerank.
  Financial text has exact-match terms (tickers, "Item 1A", dollar figures) where
  BM25 wins; conceptual questions need dense.
- **Chunking is citation-aware**: 10-K/10-Q chunked by section (Item 1A, Item 7 MD&A...);
  transcripts chunked by speaker turn (prepared remarks vs Q&A). Section anchors and
  char offsets are stored in chunk metadata — they ARE the citation system.
- **Cell agent contract**: `answer_cell(doc_id, question) -> CellResult(answer,
  citations[], cost, latency)`. One question x one document. The matrix engine fans
  out N*M cell jobs with bounded concurrency and partial-result tolerance.
- Default model `gpt-4o-mini`; model/provider must stay swappable via `src/core/config.py`.

## Roadmap (build in this order)

1. **Phase 1 — Pipeline**: EDGAR HTML -> section parser -> chunker -> embeddings ->
   Postgres. Then single-cell QA with citations (`/ask` endpoint).
2. **Phase 2 — Matrix engine**: N docs x M questions grid; eval harness (50–100
   labeled Q/A pairs, accuracy table goes in README); observability (structured logs,
   cost-per-cell, latency).
3. **Phase 3 — ONE differentiator only** (avoid feature sprawl): transcript sentiment
   column, OR fine-tuned extractor benchmarked vs gpt-4o-mini, OR multi-tenant auth.

## Engineering rules

- **Day-2 checklist is non-negotiable**: structured logging (every LLM call logs
  model, tokens in/out, latency, estimated cost, request_id), eval set before
  "improving" anything, model fallback chain, daily cost budget (`DAILY_BUDGET_USD`).
  No logs = no evals = no iteration.
- Every retrieval/prompt/chunking change must be justified by the eval harness,
  not vibes. "Improved" without a number is an assertion.
- Pydantic models for all LLM structured outputs. Type hints everywhere.
- Tests: `make test`. Lint: `make lint` (ruff, line length 100).
- Never commit `.env` (contains Wan Li's email + API keys). `.env.example` stays generic.
- Camp lecture materials may live in `docs/camp/` locally — that folder is gitignored
  and must never be committed (copyrighted course content).

## Context about the author

Wan Li (goes by **Scarlett Li** professionally) is targeting AI/ML engineering
roles. She is simultaneously building PixGen (an AI image-gen product with a
collaborator, Ethan, who also has a stock-research tool called Conviction). This
repo is HER solo project. When explaining non-trivial design decisions, be
explicit about the why — she needs to be able to whiteboard every component in
interviews without assistance.

**Identity rules (don't mix these up):**
- **Git commits** → author `Scarlett Li <scarlettli2023@gmail.com>` (portfolio name).
- **SEC EDGAR User-Agent** → `Wan Li scarlettli2023@gmail.com` (legal name; SEC
  fair-access policy requires real identity). Lives in `.env` as `EDGAR_USER_AGENT`,
  never hard-coded.
