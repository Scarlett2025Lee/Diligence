"""Retrieval eval: BM25-only vs dense-only vs hybrid on testset.jsonl.

Calls the project's retrieval functions exactly as the app does — no
retrieval code is modified or reimplemented here:

    bm25   -> src.retrieval.bm25.bm25_search(query, corpus_chunks, k)
    dense  -> src.retrieval.dense.dense_search(query_vector, None, k)
    hybrid -> src.retrieval.hybrid.hybrid_search(query, None, k)

All three modes search the WHOLE corpus (doc_ids=None) with identical
top-k, so cross-company confusion counts against every mode equally.

Metric definitions (several questions have 2-3 gold chunk ids that all
contain the answer — overlap duplicates and 10-K/10-Q restatements):
    recall@k = fraction of questions with >=1 gold chunk in the top k
    MRR      = mean over questions of 1/rank of the first gold chunk in
               the top 10 (0 if no gold chunk is retrieved)

Usage:
    python run_eval.py [--testset testset.jsonl] [--k 10]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.embeddings.client import EmbeddingClient
from src.retrieval.bm25 import bm25_search
from src.retrieval.dense import dense_search
from src.retrieval.hybrid import _load_chunks, hybrid_search

MODES = ("bm25", "dense", "hybrid")
TYPES = ("exact", "semantic", "section")


def load_testset(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    bad = [r["id"] for r in rows if not r.get("relevant_chunk_ids")]
    if bad:
        sys.exit(f"Questions without gold chunk ids (run fill_chunk_ids.py): {bad}")
    return rows


def retrieve_all(rows: list[dict], k: int) -> dict[str, dict[str, list[int]]]:
    """Return {mode: {question_id: top-k chunk ids, best first}}."""
    embedder = EmbeddingClient()
    corpus = _load_chunks(None)  # same loader hybrid_search uses for BM25
    print(f"corpus: {len(corpus)} chunks | {len(rows)} questions | k={k}", file=sys.stderr)

    results: dict[str, dict[str, list[int]]] = {m: {} for m in MODES}
    for i, row in enumerate(rows, 1):
        q = row["query"]
        results["bm25"][row["id"]] = [
            h.chunk.id for h in bm25_search(q, corpus, k=k)
        ]
        qvec = embedder.embed_batch([q]).vectors[0]
        results["dense"][row["id"]] = [
            h.chunk.id for h in dense_search(qvec, None, k=k)
        ]
        results["hybrid"][row["id"]] = [
            h.chunk_id for h in hybrid_search(q, None, k=k, embedder=embedder)
        ]
        print(f"  [{i}/{len(rows)}] {row['id']}", file=sys.stderr)
    return results


def first_gold_rank(retrieved: list[int], gold: set[int]) -> int | None:
    for rank, cid in enumerate(retrieved, start=1):
        if cid in gold:
            return rank
    return None


def evaluate(rows: list[dict], results: dict[str, dict[str, list[int]]], k: int):
    overall = {}   # mode -> (recall@5, recall@k, mrr)
    by_type = {}   # mode -> {type: recall@k}
    for mode in MODES:
        hits5 = hitsk = rr_sum = 0
        type_hits: dict[str, int] = defaultdict(int)
        type_totals: dict[str, int] = defaultdict(int)
        for row in rows:
            gold = {int(c) for c in row["relevant_chunk_ids"]}
            rank = first_gold_rank(results[mode][row["id"]], gold)
            type_totals[row["type"]] += 1
            if rank is not None:
                hitsk += 1
                rr_sum += 1.0 / rank
                type_hits[row["type"]] += 1
                if rank <= 5:
                    hits5 += 1
        n = len(rows)
        overall[mode] = (hits5 / n, hitsk / n, rr_sum / n)
        by_type[mode] = {
            t: type_hits[t] / type_totals[t] for t in TYPES if type_totals[t]
        }
    return overall, by_type


def print_tables(overall, by_type, k: int) -> str:
    lines = []
    lines.append(f"|Mode|recall@5|recall@{k}|MRR|")
    lines.append("|-|-|-|-|")
    for mode in MODES:
        r5, rk, mrr = overall[mode]
        lines.append(f"|{mode}|{r5:.2f}|{rk:.2f}|{mrr:.2f}|")
    lines.append("")
    lines.append(f"### By query type (recall@{k})")
    lines.append("")
    lines.append("|Mode|" + "|".join(TYPES) + "|")
    lines.append("|-|" + "-|" * len(TYPES))
    for mode in MODES:
        cells = "|".join(f"{by_type[mode].get(t, 0.0):.2f}" for t in TYPES)
        lines.append(f"|{mode}|{cells}|")
    out = "\n".join(lines)
    print(out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--testset", default=str(pathlib.Path(__file__).parent / "testset.jsonl"))
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args()

    rows = load_testset(args.testset)
    results = retrieve_all(rows, k=args.k)
    overall, by_type = evaluate(rows, results, k=args.k)
    print_tables(overall, by_type, k=args.k)

    # Per-question detail for debugging retrieval failures.
    detail_path = pathlib.Path(args.testset).with_name("last_run_detail.jsonl")
    with open(detail_path, "w", encoding="utf-8") as f:
        for row in rows:
            gold = {int(c) for c in row["relevant_chunk_ids"]}
            f.write(json.dumps({
                "id": row["id"], "type": row["type"], "company": row["company"],
                "gold": sorted(gold),
                **{m: {"top": results[m][row["id"]],
                       "first_gold_rank": first_gold_rank(results[m][row["id"]], gold)}
                   for m in MODES},
            }) + "\n")
    print(f"\nper-question detail -> {detail_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
