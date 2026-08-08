"""Query decomposition agent.

The Hebbia insight: don't stuff a complex question into one model call.
'Compare debt covenants across these filings' becomes:
  1. locate covenant sections (retrieval-heavy)
  2. extract terms per filing (extraction-heavy)
  3. synthesize comparison (reasoning-heavy)
Each sub-step can route to a different model. TODO(phase-2).
"""
