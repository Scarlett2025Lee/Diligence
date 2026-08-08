"""Retrieval unit tests.

Pure-logic tests for BM25 ranking and RRF fusion. The hybrid_search
end-to-end test is skipped because it would need a live Postgres with
populated vectors — that's an integration test, not a unit test, and the
constituent pieces are covered here.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.retrieval.bm25 import bm25_search, tokenize
from src.retrieval.hybrid import rrf_fuse


@dataclass
class _FakeChunk:
    """Stand-in for a ChunkRow that only carries what BM25 needs."""
    id: int
    text: str


CORPUS = [
    _FakeChunk(1, "Total net sales were $391 billion driven by Services growth."),
    _FakeChunk(2, "Mine safety disclosures are required by Section 1503."),
    _FakeChunk(3, "Apple Intelligence is a new investment area in fiscal 2024."),
    _FakeChunk(4, "Revenue from iPhone declined modestly year over year."),
    _FakeChunk(5, "The Company faces risks from supply chain concentration."),
]


def test_tokenize_keeps_dollar_figures_intact():
    tokens = tokenize("Revenue was $391.0B, up 2% YoY.")
    assert "$391.0b" in tokens
    assert "2" in tokens
    assert "yoy" in tokens


def test_tokenize_lowercases_and_splits_on_punctuation():
    tokens = tokenize("Item 1A, Risk Factors—(continued)")
    assert "item" in tokens
    assert "1a" in tokens
    assert "factors" in tokens
    assert "continued" in tokens


def test_bm25_returns_revenue_chunk_first_for_revenue_query():
    hits = bm25_search("total revenue and growth", CORPUS, k=3)
    assert hits, "expected at least one hit"
    # Chunks 1 and 4 are the revenue ones; either is acceptable as #1.
    assert hits[0].chunk.id in (1, 4)
    assert hits[0].score > 0


def test_bm25_filters_zero_score_results():
    # "spaceship" appears in nothing; expect no hits, not a tail of zeros.
    hits = bm25_search("spaceship reentry", CORPUS, k=5)
    assert hits == []


def test_bm25_empty_inputs_return_empty():
    assert bm25_search("anything", [], k=5) == []
    assert bm25_search("", CORPUS, k=5) == []


def test_rrf_fuse_prefers_items_ranked_high_in_both():
    # Item 1 is top of list A and top of list B → should be #1 overall.
    fused = rrf_fuse([[1, 2, 3], [1, 3, 2]], k_const=60)
    assert fused[0][0] == 1
    # Items 2 and 3 each appear in both lists too, with mixed ranks.
    assert {item_id for item_id, _ in fused} == {1, 2, 3}


def test_rrf_fuse_handles_missing_items():
    # 4 appears in list A only, 5 in list B only. Each gets one contribution.
    fused = rrf_fuse([[1, 4], [1, 5]], k_const=60)
    assert fused[0][0] == 1  # in both → biggest score
    score_by_id = dict(fused)
    assert score_by_id[1] > score_by_id[4]
    assert score_by_id[1] > score_by_id[5]


def test_rrf_fuse_uses_one_indexed_ranks():
    # With k_const=0 the first-place item should score exactly 1/1 = 1.0.
    fused = rrf_fuse([[42]], k_const=0)
    assert fused[0] == (42, 1.0)


def test_rrf_fuse_empty_input_is_empty():
    assert rrf_fuse([[], []]) == []
    assert rrf_fuse([]) == []
