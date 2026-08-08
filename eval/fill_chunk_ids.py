"""
Fill relevant_chunk_ids in testset_draft.jsonl by matching each question's
pasted answer_text against your chunks table in Postgres.

Usage:
    python fill_chunk_ids.py --in testset_draft.jsonl --out testset.jsonl

Adjust the CONFIG block to match your schema, and set DATABASE_URL in your env.
Questions with empty answer_text are skipped (and reported at the end).
"""

import argparse
import json
import os
import re
import sys

import psycopg as psycopg2  # project uses psycopg v3; connect/cursor API is compatible here

# ---------------- CONFIG: adjust to your schema ----------------
# ticker lives on documents, not chunks, so TABLE is a join expression.
TABLE = "chunks c JOIN documents d ON d.doc_id = c.doc_id"
ID_COL = "c.id"           # chunk id column
TEXT_COL = "c.text"       # chunk text column
TICKER_COL = "d.ticker"   # column identifying the company; set to None if absent
# ----------------------------------------------------------------


def normalize(s: str) -> str:
    """Collapse whitespace so PDF/HTML extraction quirks don't break matching."""
    return re.sub(r"\s+", " ", s).strip()


def find_chunks(cur, answer_text: str, ticker: str) -> list:
    """Try exact substring match first, then fall back to the longest
    distinctive fragment (helps when chunk boundaries split the sentence)."""
    probe = normalize(answer_text)
    candidates = [probe]
    # Fallback fragments: first ~8 words and last ~8 words of the answer
    words = probe.split()
    if len(words) > 8:
        candidates.append(" ".join(words[:8]))
        candidates.append(" ".join(words[-8:]))

    for fragment in candidates:
        pattern = "%" + fragment.replace("%", r"\%").replace("_", r"\_") + "%"
        if TICKER_COL:
            cur.execute(
                f"SELECT {ID_COL} FROM {TABLE} "
                f"WHERE regexp_replace({TEXT_COL}, '\\s+', ' ', 'g') ILIKE %s "
                f"AND {TICKER_COL} = %s",
                (pattern, ticker),
            )
        else:
            cur.execute(
                f"SELECT {ID_COL} FROM {TABLE} "
                f"WHERE regexp_replace({TEXT_COL}, '\\s+', ' ', 'g') ILIKE %s",
                (pattern,),
            )
        rows = cur.fetchall()
        if rows:
            return [r[0] for r in rows]
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="testset_draft.jsonl")
    ap.add_argument("--out", dest="out", default="testset.jsonl")
    args = ap.parse_args()

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        sys.exit("Set DATABASE_URL, e.g. postgresql://user:pass@localhost:5432/db")

    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

    filled, skipped, unmatched, multi = [], [], [], []
    with open(args.inp) as f:
        for line in f:
            if not line.strip():
                continue
            ex = json.loads(line)
            if not ex.get("answer_text", "").strip():
                skipped.append(ex["id"])
                continue
            ids = find_chunks(cur, ex["answer_text"], ex.get("company", ""))
            ex["relevant_chunk_ids"] = [str(i) for i in ids]
            if not ids:
                unmatched.append(ex["id"])
            elif len(ids) > 3:
                multi.append((ex["id"], len(ids)))
            filled.append(ex)

    with open(args.out, "w") as f:
        for ex in filled:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"Wrote {len(filled)} questions to {args.out}")
    if skipped:
        print(f"Skipped (no answer_text pasted yet): {', '.join(skipped)}")
    if unmatched:
        print(f"NO MATCH — check the pasted text against your chunks: "
              f"{', '.join(unmatched)}")
    if multi:
        print("Matched many chunks (paste a more distinctive sentence?): "
              + ", ".join(f"{q} ({n} hits)" for q, n in multi))


if __name__ == "__main__":
    main()
