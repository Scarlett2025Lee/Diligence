"""Chunking strategy.

Filings and transcripts need different treatment:
  - 10-K/10-Q: section-aware chunking (Item 1A Risk Factors, Item 7 MD&A...)
    Section anchors ARE the citation system — preserve them in metadata.
  - Transcripts: speaker-turn chunking (prepared remarks vs Q&A matters).

Each chunk carries: doc_id, source_type, section/speaker, char offsets.
TODO(phase-1): implement section parser + token-aware splitter.
"""
