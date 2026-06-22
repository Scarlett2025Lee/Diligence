"""BM25 search over a chunk corpus.

In-process via rank_bm25. For one filing's ~400 chunks, building the
index per query costs ~5–10ms, which is dwarfed by the dense pgvector
roundtrip and the LLM call downstream. When the corpus grows past
~50k chunks we'll either persist a tsvector + GIN column, or move to
a dedicated search backend.

Tokenization: keep dollar figures and decimals intact ("$391.0B" stays
as one token after lowercasing), since financial text leans on those.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

# Match alphanumeric runs plus embedded `.` and `$` so "$391.0B" survives
# as a single token. Anything else (commas, parens, em-dashes) is a split.
_TOKEN_RE = re.compile(r"[\$\w][\w\.\$]*")


def tokenize(text: str) -> list[str]:
    """Lowercase tokenize, keeping dollar figures intact.

    Trailing periods are stripped so a sentence-ending "YoY." matches
    a body-text "YoY"; internal periods inside "$391.0B" are preserved.
    """
    raw = _TOKEN_RE.findall(text.lower())
    return [t for t in (tok.rstrip(".") for tok in raw) if t]


@dataclass(frozen=True)
class Bm25Hit:
    """One BM25 result. `chunk` is whatever opaque object the caller passed in
    (typically a ChunkRow); we don't depend on its type here so the unit
    tests can use plain dataclasses."""
    chunk: object
    score: float


def bm25_search(query: str, chunks: list, k: int) -> list[Bm25Hit]:
    """Score `chunks` against `query`, return the top-k by BM25.

    `chunks` is a sequence of objects that each have a `.text` attribute.
    Empty corpus or query returns []; an empty query gives no useful
    ranking and we'd rather skip than embarrass ourselves with random
    order.
    """
    if not chunks:
        return []
    q_tokens = tokenize(query)
    if not q_tokens:
        return []

    corpus_tokens = [tokenize(c.text) for c in chunks]
    bm25 = BM25Okapi(corpus_tokens)
    scores = bm25.get_scores(q_tokens)
    ranked = sorted(
        ((c, float(s)) for c, s in zip(chunks, scores)),
        key=lambda x: x[1],
        reverse=True,
    )
    # Drop zero-score hits — they share no tokens with the query, including
    # them in the ranked list pollutes RRF with effectively random tail.
    return [Bm25Hit(chunk=c, score=s) for c, s in ranked[:k] if s > 0]
