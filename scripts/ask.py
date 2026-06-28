"""CLI: python -m scripts.ask "question" --doc-id ACCESSION [-k 5]

Runs the cell agent against the live DB. Prints the answer, then each
citation with its quoted passage so you can eyeball grounding quality.

Cost per call is ~$0.0003 with gpt-4o-mini at default k=5. The daily
budget guard in core.budget protects you from a runaway loop.
"""
from __future__ import annotations

import argparse

from src.agents import CellAgent
from src.core.logging import configure_logging


def main(question: str, doc_id: str, k: int) -> None:
    configure_logging()
    agent = CellAgent()
    result = agent.answer_cell(doc_id=doc_id, question=question, k=k)

    print()
    if result.status == "error":
        print(f"ERROR: {result.error}")
        print(f"latency={result.latency_ms}ms")
        return

    print(f"Q: {question}")
    print(f"A: {result.answer}\n")
    print(f"cost=${result.cost_usd:.6f}  latency={result.latency_ms}ms  "
          f"citations={len(result.citations)}\n")
    for i, c in enumerate(result.citations, 1):
        snippet = c.quote.replace("\n", " ")[:300]
        print(f"  [{i}] Item {c.item} — {c.section_title}  (chunk_id={c.chunk_id})")
        print(f"      {snippet}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--doc-id", required=True, help="EDGAR accession number")
    parser.add_argument("-k", type=int, default=5, help="Chunks to retrieve")
    args = parser.parse_args()
    main(args.question, args.doc_id, args.k)
