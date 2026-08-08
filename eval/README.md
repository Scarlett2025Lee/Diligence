# Retrieval Evaluation

Benchmark comparing BM25-only, dense-only, and hybrid (BM25 + dense + rerank)
retrieval on finance-specific queries over SEC filings.

## Eval corpus (frozen 2026-08-07)

* **Companies (10):** AAOI, AXTI, AMD, DELL, IBM, MU, AMZN, MSFT, AAPL, GOOGL
* **Filings:** latest 10-K + latest 10-Q per company (20 filings)
* **Chunks:** 2,853 (see amendment below)

> **Post-freeze amendment (2026-08-07):** IBM's 10-K incorporates its MD&A and
> financial statements by reference from Exhibit 13; the original ingest
> captured only the 54-chunk wrapper. Exhibit 13 was ingested and embedded,
> bringing IBM from 54 to 277 chunks and the corpus from 2,630 to 2,853.

## Test set

`testset.jsonl` — 40 queries with hand-labeled ground-truth chunk IDs, three types:

|Type|Count|What it tests|
|-|-|-|
|exact|17|Specific figures/facts (BM25-favorable)|
|semantic|13|Paraphrase, no shared wording with filing (dense-favorable)|
|section|10|Item 1A / MD&A / Item 7A lookups|

### Fields

```json
{"id": "q01", "type": "exact", "company": "AMD", "filing": "10-K",
 "query": "...", "answer_text": "<sentence pasted from the filing>",
 "relevant_chunk_ids": ["..."]}
```

## How the test set was built

1. Each question's `answer_text` was filled in `testset_draft.jsonl` by pasting
the exact sentence from the filing that answers it; questions with no answer
in the corpus were deleted, keeping the three type counts roughly balanced.
2. `python fill_chunk_ids.py --in testset_draft.jsonl --out testset.jsonl`
resolved ground-truth chunk IDs; NO MATCH items were fixed by hand.
3. ~5 questions were spot-checked by looking up the matched chunk ID and
confirming it contains the answer.

## Running the eval

```bash
python run_eval.py
```

Runs all three retrieval modes with identical k over the frozen corpus, then
paste the results into the tables below.

## Results

|Mode|recall@5|recall@10|MRR|
|-|-|-|-|
|bm25|0.15|0.33|0.07|
|dense|0.45|0.57|0.27|
|hybrid|0.35|0.53|0.21|

### By query type (recall@10)

|Mode|exact|semantic|section|
|-|-|-|-|
|bm25|0.29|0.31|0.40|
|dense|0.59|0.38|0.80|
|hybrid|0.59|0.46|0.50|

Dense-only wins in the whole-corpus setting (0.57 vs 0.53 recall@10, 0.27 vs 0.21 MRR); BM25 underperforms even on exact queries because query phrasing shares few tokens with filing language; equal-weight RRF lets BM25's noise drag hybrid below dense, most visibly on section lookups (0.80 → 0.50); doc-scoped retrieval — how the production agent actually queries — is the untested setting where hybrid may fare better.

## Honesty rules

* Same k across all modes; same frozen corpus for every run.
* No tuning fusion weights against this set — hold out 10 queries if tuning.
* Report absolute numbers, not just relative improvement.

