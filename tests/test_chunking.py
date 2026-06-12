"""Chunker tests.

We're checking the contract, not the exact byte counts: chunks stay under
the target, offsets round-trip back to the section body, and overlap
exists between consecutive chunks.
"""
from __future__ import annotations

from src.ingestion.chunking import (
    DEFAULT_TARGET_TOKENS,
    Chunk,
    chunk_section,
)
from src.ingestion.sections import Section


def _make_section(body: str, item: str = "1A", title: str = "Risk Factors") -> Section:
    return Section(
        item=item,
        title=title,
        text=body,
        char_start=0,
        char_end=len(body),
    )


def test_short_section_produces_one_chunk():
    body = "Our business depends on a small number of large customers."
    section = _make_section(body)

    chunks = chunk_section(section, doc_id="acc-1")

    assert len(chunks) == 1
    assert chunks[0].text == body
    assert chunks[0].body_start == 0
    assert chunks[0].body_end == len(body)
    assert chunks[0].item == "1A"
    assert chunks[0].section_title == "Risk Factors"
    assert chunks[0].chunk_index == 0


def test_long_section_produces_multiple_chunks_under_target():
    # Build a body with many paragraphs that together blow past the target.
    paragraph = (
        "The company faces significant competition from established players "
        "and new entrants alike. Pricing pressure has intensified over the "
        "past several quarters as customers consolidate their vendor base "
        "and demand longer payment terms. "
    ) * 4  # ~880 chars per paragraph
    body = "\n\n".join(f"Paragraph {i}. {paragraph}" for i in range(20))
    section = _make_section(body)

    chunks = chunk_section(section, doc_id="acc-1", target_tokens=400)

    assert len(chunks) >= 3
    target_chars = 400 * 4
    # Allow a small slack: a chunk can run slightly over if the last
    # paragraph put it over the line — but never by more than one paragraph.
    for c in chunks:
        assert len(c.text) <= target_chars + len(paragraph) + 20


def test_offsets_round_trip_to_section_body():
    body = "\n\n".join(f"Paragraph {i}. " + ("x " * 200) for i in range(10))
    section = _make_section(body)

    chunks = chunk_section(section, doc_id="acc-1", target_tokens=300)

    for c in chunks:
        # The chunk text is exactly the slice the offsets claim.
        assert section.text[c.body_start : c.body_end] == c.text


def test_consecutive_chunks_overlap():
    body = "\n\n".join(f"Paragraph {i}. " + ("y " * 100) for i in range(15))
    section = _make_section(body)

    chunks = chunk_section(section, doc_id="acc-1", target_tokens=200, overlap_tokens=60)

    assert len(chunks) >= 2
    for prev, nxt in zip(chunks, chunks[1:]):
        # Overlap means the next chunk starts before the previous one ended.
        assert nxt.body_start < prev.body_end


def test_chunk_indexes_are_sequential():
    body = "\n\n".join(f"P{i}. " + ("z " * 80) for i in range(12))
    section = _make_section(body)

    chunks = chunk_section(section, doc_id="acc-1", target_tokens=200)

    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_giant_paragraph_falls_back_to_sentence_split():
    # One paragraph, many sentences, total length >> target.
    sentence = "This is a sentence about widget revenue and margins. "
    body = sentence * 60  # one paragraph, ~3000 chars, no \n\n boundaries
    section = _make_section(body)

    chunks = chunk_section(section, doc_id="acc-1", target_tokens=200)

    assert len(chunks) >= 2
    # Reassembling chunks should cover the full body (modulo overlap).
    reassembled_set = set()
    for c in chunks:
        reassembled_set.update(range(c.body_start, c.body_end))
    # No char in the body should be missing from every chunk.
    assert reassembled_set == set(range(len(body)))


def test_default_target_is_reasonable_for_embedding():
    # The default should produce chunks well under the 8k-token embedding limit.
    assert DEFAULT_TARGET_TOKENS < 1500


def test_chunk_carries_doc_id_and_item_for_citation():
    section = _make_section("short body of risk factors. " * 5, item="7", title="MD&A")
    chunks = chunk_section(section, doc_id="0000320193-24-000123")
    assert isinstance(chunks[0], Chunk)
    assert chunks[0].doc_id == "0000320193-24-000123"
    assert chunks[0].item == "7"
    assert chunks[0].section_title == "MD&A"
