"""CLI: python -m scripts.search "question" [--doc-id ACCESSION] [-k 5]

Runs hybrid retrieval against the live DB and prints the top-k chunks
with their per-source ranks. Useful for sanity-checking retrieval quality
before wiring up the cell agent.
"""
from __future__ import annotations

import argparse

from src.core.logging import configure_logging
from src.retrieval import hybrid_search


def main(question: str, doc_ids: list[str] | None, k: int) -> None:
    configure_logging()
    hits = hybrid_search(question, doc_ids=doc_ids, k=k)
    if not hits:
        print("no hits")
        return
    print(f"top {len(hits)} hits for: {question!r}\n")
    for i, h in enumerate(hits, 1):
        snippet = h.text.replace("\n", " ")[:180]
        print(
            f"{i:>2}. score={h.score:.4f}  "
            f"bm25={h.bm25_rank or '-'}  dense={h.dense_rank or '-'}  "
            f"Item {h.item}  ({h.doc_id})"
        )
        print(f"    {snippet}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("question", help="Natural-language question")
    parser.add_argument(
        "--doc-id",
        action="append",
        dest="doc_ids",
        help="Restrict search to this filing accession number. "
             "Repeat to allow multiple.",
    )
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args()
    main(args.question, args.doc_ids, args.k)
