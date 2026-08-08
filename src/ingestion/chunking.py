"""Chunking strategy.

Filings and transcripts need different treatment:
  - 10-K/10-Q: section-aware chunking (Item 1A Risk Factors, Item 7 MD&A...).
    Section anchors ARE the citation system — preserve them in metadata.
  - Transcripts: speaker-turn chunking (prepared remarks vs Q&A matters). [TODO]

Sizing: target ~600 tokens per chunk, ~80 tokens of overlap. Why these numbers:
  - 600 tokens lands well under the embedding model's 8k limit and leaves
    plenty of room when we concat ~6 chunks into a prompt.
  - Overlap protects answers whose key sentence straddles a boundary —
    without it, retrieval could pull a chunk that ends mid-thought.

Token counting: we approximate as 4 chars/token, which is the standard
English rule of thumb. When we wire up the embedding client we'll swap in
tiktoken for exact counts; the chunk boundaries don't need to be exact,
they just need to be predictable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.ingestion.sections import Section

# 4 chars/token is the typical English ratio. See OpenAI's "What are tokens"
# guidance. Good enough for boundary decisions; exact counts come from
# tiktoken at embed time.
_CHARS_PER_TOKEN = 4

DEFAULT_TARGET_TOKENS = 600
DEFAULT_OVERLAP_TOKENS = 80

# Sentence splitter: break on . ! ? followed by whitespace + capital letter,
# preserving the terminator. Not perfect for "Inc." / "Mr." but fine for
# 10-K prose where most sentences are long and well-formed.
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"])")


@dataclass(frozen=True)
class Chunk:
    doc_id: str          # filing identifier (e.g. accession number)
    item: str            # 10-K item id, e.g. "1A", "7"
    section_title: str   # human title carried from Section
    text: str            # chunk body
    body_start: int      # offset into Section.text (NOT the raw filing)
    body_end: int        # offset into Section.text
    chunk_index: int     # 0-based position within the section


def chunk_section(
    section: Section,
    doc_id: str,
    target_tokens: int = DEFAULT_TARGET_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    """Split one Section into ordered, slightly-overlapping Chunks.

    Strategy:
      1. Split the body into paragraphs (`\\n\\n` boundaries).
      2. Greedily pack paragraphs until the next one would overflow
         `target_tokens`. Emit a chunk.
      3. Carry roughly `overlap_tokens` of tail text into the next chunk
         so a sentence sitting on the boundary appears in both.
      4. If a single paragraph is already larger than the target, fall back
         to sentence-level packing inside it. If a single sentence is also
         too big, hard-split on character count — rare but possible in
         tables flattened from HTML.
    """
    target_chars = target_tokens * _CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * _CHARS_PER_TOKEN

    units = _split_into_units(section.text, target_chars)
    if not units:
        return []

    chunks: list[Chunk] = []
    current: list[tuple[int, int, str]] = []  # (start, end, text) tuples
    current_chars = 0

    def flush() -> None:
        nonlocal current, current_chars
        if not current:
            return
        start = current[0][0]
        end = current[-1][1]
        text = section.text[start:end]
        chunks.append(
            Chunk(
                doc_id=doc_id,
                item=section.item,
                section_title=section.title,
                text=text,
                body_start=start,
                body_end=end,
                chunk_index=len(chunks),
            )
        )
        # Seed the next chunk with the tail of this one so we get overlap.
        current, current_chars = _tail_overlap(current, overlap_chars)

    for unit in units:
        u_start, u_end, u_text = unit
        u_len = u_end - u_start
        if current and current_chars + u_len > target_chars:
            flush()
        current.append(unit)
        current_chars += u_len

    flush()
    # The final flush re-seeds `current` with tail overlap; drop it.
    return chunks


def _split_into_units(body: str, target_chars: int) -> list[tuple[int, int, str]]:
    """Return atomic packing units as (start, end, text) tuples.

    A unit is normally a paragraph. Paragraphs longer than `target_chars`
    are broken into sentences; sentences longer than `target_chars` are
    hard-split on char count. Offsets are always relative to `body`.
    """
    units: list[tuple[int, int, str]] = []
    for p_start, p_end in _paragraph_spans(body):
        p_text = body[p_start:p_end]
        if len(p_text) <= target_chars:
            units.append((p_start, p_end, p_text))
            continue
        for s_start, s_end in _sentence_spans(p_text):
            s_abs_start = p_start + s_start
            s_abs_end = p_start + s_end
            s_text = body[s_abs_start:s_abs_end]
            if len(s_text) <= target_chars:
                units.append((s_abs_start, s_abs_end, s_text))
                continue
            # Pathological case: one "sentence" longer than the target.
            # Hard-split into target-sized slabs; we accept the loss of
            # semantic boundary because the alternative is no chunk at all.
            for off in range(0, len(s_text), target_chars):
                a = s_abs_start + off
                b = min(s_abs_start + off + target_chars, s_abs_end)
                units.append((a, b, body[a:b]))
    return units


def _paragraph_spans(text: str) -> list[tuple[int, int]]:
    """Yield (start, end) for each non-empty paragraph in `text`."""
    spans: list[tuple[int, int]] = []
    pos = 0
    for m in re.finditer(r"\n\s*\n", text):
        end = m.start()
        if end > pos and text[pos:end].strip():
            spans.append((pos, end))
        pos = m.end()
    if pos < len(text) and text[pos:].strip():
        spans.append((pos, len(text)))
    return spans


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    """Yield (start, end) for each sentence in `text`."""
    if not text:
        return []
    spans: list[tuple[int, int]] = []
    pos = 0
    for m in _SENTENCE_RE.finditer(text):
        spans.append((pos, m.start()))
        pos = m.end()
    spans.append((pos, len(text)))
    return [(a, b) for a, b in spans if text[a:b].strip()]


def _tail_overlap(
    units: list[tuple[int, int, str]], overlap_chars: int
) -> tuple[list[tuple[int, int, str]], int]:
    """Return the trailing units whose combined length is <= overlap_chars.

    Picks from the end backwards. If no whole unit fits we return empty —
    we'd rather skip overlap than slice a unit awkwardly and confuse
    citation offsets.
    """
    if overlap_chars <= 0 or not units:
        return [], 0
    kept: list[tuple[int, int, str]] = []
    total = 0
    for unit in reversed(units):
        u_len = unit[1] - unit[0]
        if total + u_len > overlap_chars:
            break
        kept.append(unit)
        total += u_len
    kept.reverse()
    return kept, total
