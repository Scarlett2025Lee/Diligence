"""Section parser tests.

Synthetic 10-K fixture exercises the things that actually break in the wild:
  - Items appearing once in the TOC and again as real headers (most filings).
  - Sub-items like 1A / 7A.
  - Inline HTML tags inside header text (filings rarely use clean <h2>).
  - A section short enough to be dropped (TOC remnant).
"""
from __future__ import annotations

from src.ingestion.sections import ITEM_TITLES, html_to_text, parse_sections


FIXTURE_HTML = """
<html><body>
<h1>ACME CORP 10-K</h1>

<div>Table of Contents</div>
<table>
  <tr><td>Item 1.</td><td>Business</td><td>3</td></tr>
  <tr><td>Item 1A.</td><td>Risk Factors</td><td>10</td></tr>
  <tr><td>Item 7.</td><td>MD&amp;A</td><td>30</td></tr>
  <tr><td>Item 7A.</td><td>Quantitative Disclosures</td><td>55</td></tr>
  <tr><td>Item 8.</td><td>Financial Statements</td><td>60</td></tr>
</table>

<p><b>Item 1. Business</b></p>
<p>ACME Corp designs and sells widgets to industrial customers across North
America and Europe. The company was founded in 1998 and is headquartered in
Cleveland, Ohio. Revenue comes primarily from the sale of physical widgets
and a smaller services attach.</p>

<p><b>Item 1A. Risk Factors</b></p>
<p>Our business is subject to a number of risks. Demand for widgets is
cyclical and tracks industrial production. A loss of any of our top three
customers, which together represent 40% of revenue, would materially harm
results of operations. We also depend on a single supplier for our key
input material.</p>

<p><b>Item 7. Management's Discussion and Analysis</b></p>
<p>Revenue for fiscal 2024 grew 12% year over year to $1.2 billion, driven
by price increases and volume growth in the industrial segment. Gross
margin expanded 180 basis points to 42.3% as raw material costs eased in
the second half. Operating expenses grew more slowly than revenue.</p>

<p><b>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</b></p>
<p>We are exposed to interest-rate risk on our variable-rate debt and to
foreign-currency risk on euro-denominated sales. A hypothetical 100 basis
point rise in interest rates would increase annual interest expense by
approximately $4 million based on year-end balances.</p>

<p><b>Item 8. Financial Statements and Supplementary Data</b></p>
<p>The audited consolidated financial statements and accompanying notes,
together with the report of our independent registered public accounting
firm, are included beginning on page F-1 of this Annual Report on Form
10-K and are incorporated herein by reference.</p>

</body></html>
"""


def test_html_to_text_strips_tags_and_normalizes_whitespace():
    text = html_to_text(FIXTURE_HTML)
    assert "<p>" not in text
    assert "  " not in text  # collapsed
    assert "MD&A" in text    # entities decoded


def test_parse_sections_returns_each_item_in_order():
    sections = parse_sections(FIXTURE_HTML)
    items = [s.item for s in sections]
    assert items == ["1", "1A", "7", "7A", "8"]


def test_parse_sections_skips_toc_and_keeps_body():
    sections = parse_sections(FIXTURE_HTML)
    risk = next(s for s in sections if s.item == "1A")
    # Header text from the filing, not the canonical fallback.
    assert risk.title.lower().startswith("risk factors")
    # Body has the actual risk-factor sentence, not the TOC entry.
    assert "cyclical" in risk.text
    assert "Table of Contents" not in risk.text


def test_char_offsets_align_with_cleaned_text():
    text = html_to_text(FIXTURE_HTML)
    sections = parse_sections(FIXTURE_HTML)
    for s in sections:
        # The header line at char_start should mention "Item <id>".
        snippet = text[s.char_start : s.char_start + 80].lower()
        assert f"item {s.item.lower()}" in snippet
        # Body content from .text should appear inside the slice.
        assert s.text[:40] in text[s.char_start : s.char_end]


def test_section_body_excludes_header_line():
    """The body must not repeat the header — wastes tokens + pollutes embeddings.

    Realistic 10-K HTML wraps the header in its own <p> so html_to_text
    emits a blank line before the body. The parser must skip that header
    line cleanly; this test pins that against regressions.
    """
    html = (
        "<html><body>"
        "<p>Item 1A. Risk Factors ............ 10</p>"  # TOC
        "<p><b>Item 1A. Risk Factors</b></p>"            # real header
        "<p>" + ("The Company's business is subject to risks. " * 10) + "</p>"
        "</body></html>"
    )
    sections = parse_sections(html)
    risk = next(s for s in sections if s.item == "1A")
    assert not risk.text.lower().startswith("item "), (
        f"section body should not start with header line; got {risk.text[:60]!r}"
    )
    assert risk.text.startswith("The Company")


def test_title_falls_back_to_canonical_when_missing():
    # Header without a human title after the number -> use ITEM_TITLES.
    html = (
        "<html><body>"
        "<p>Item 1A.</p>"
        "<p>" + ("A" * 200) + "</p>"
        "</body></html>"
    )
    sections = parse_sections(html)
    assert len(sections) == 1
    assert sections[0].title == ITEM_TITLES["1A"]
