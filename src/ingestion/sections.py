"""10-K / 10-Q section parser.

Why this exists: Every cell-agent answer must cite a source span. In a 10-K
the natural unit of citation is the SEC item ("Item 1A. Risk Factors",
"Item 7. MD&A"), so we split the filing along those boundaries before
chunking. Each Section carries char offsets back into the cleaned text —
those offsets are what downstream chunking will turn into citation anchors.

Approach:
  1. HTML -> plain text via BeautifulSoup, preserving block-level newlines.
  2. Normalize whitespace.
  3. Find every "Item N[A-C]." header candidate by regex.
  4. Skip the table of contents: most 10-Ks list every item near the top
     with little text between entries. We resolve this by picking, for each
     item number, the LAST occurrence in the document and ignoring earlier
     ones. The genuine section header is always after the TOC.
  5. Slice the text between consecutive chosen headers -> Section bodies.

This is heuristic, not a SEC-grade parser. It targets the modern HTML 10-Ks
(2001+) which dominate EDGAR. Edge cases (amendments, embedded XBRL,
exhibit-only filings) are out of scope for Phase 1.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

# Canonical titles for each 10-K item. Used as a fallback when the filing's
# own header text is missing or noisy. Keep these aligned with Regulation S-K.
ITEM_TITLES: dict[str, str] = {
    "1": "Business",
    "1A": "Risk Factors",
    "1B": "Unresolved Staff Comments",
    "1C": "Cybersecurity",
    "2": "Properties",
    "3": "Legal Proceedings",
    "4": "Mine Safety Disclosures",
    "5": "Market for Registrant's Common Equity",
    "6": "Reserved",
    "7": "Management's Discussion and Analysis",
    "7A": "Quantitative and Qualitative Disclosures About Market Risk",
    "8": "Financial Statements and Supplementary Data",
    "9": "Changes in and Disagreements With Accountants",
    "9A": "Controls and Procedures",
    "9B": "Other Information",
    "9C": "Disclosure Regarding Foreign Jurisdictions",
    "10": "Directors, Executive Officers and Corporate Governance",
    "11": "Executive Compensation",
    "12": "Security Ownership of Certain Beneficial Owners",
    "13": "Certain Relationships and Related Transactions",
    "14": "Principal Accountant Fees and Services",
    "15": "Exhibits and Financial Statement Schedules",
    "16": "Form 10-K Summary",
}

# Item header anywhere in the line. Tolerates Unicode dashes, optional period
# after the number, optional "Part" prefix on a prior line, and stray
# whitespace from HTML rendering. The trailing lookahead requires a space or
# punctuation so "Item 1ABC" doesn't match "Item 1A".
_ITEM_RE = re.compile(
    r"(?im)^\s*item\s+(?P<num>\d{1,2})(?P<sub>[A-C])?\s*[.—–:\-]?(?=\s|$)"
)

# Section bodies shorter than this are almost certainly TOC remnants or
# a placeholder like "Item 6. [Reserved]". Kept low so we don't drop the
# legitimately-short "Reserved" item if it has at least a sentence.
_MIN_SECTION_CHARS = 120


@dataclass(frozen=True)
class Section:
    item: str            # canonical id e.g. "1A", "7"
    title: str           # human title — first non-empty line of the header, falling back to ITEM_TITLES
    text: str            # cleaned body text, header line stripped
    char_start: int      # offset into the cleaned text returned by html_to_text
    char_end: int


def html_to_text(html: str) -> str:
    """Render EDGAR HTML to whitespace-normalized plain text.

    Block elements become newlines so item headers land at the start of a
    line — `_ITEM_RE` anchors on `^` and relies on that.
    """
    soup = BeautifulSoup(html, "lxml")

    # Strip non-content nodes that otherwise inject noise into the text.
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # Force a newline after every block tag so headers don't get glued to
    # surrounding text. get_text() with a separator collapses inline tags.
    for tag in soup.find_all(
        ["p", "div", "br", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6"]
    ):
        tag.append("\n")

    text = soup.get_text(separator=" ")

    # Collapse runs of spaces/tabs but keep newlines so anchors stay aligned.
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_item_id(num: str, sub: str | None) -> str:
    return f"{int(num)}{sub.upper()}" if sub else str(int(num))


def _resolve_headers(text: str) -> list[tuple[int, str]]:
    """Return [(char_offset, item_id)] sorted by position.

    For each distinct item id we keep only the LAST match — earlier matches
    are TOC entries. We then sort the survivors by offset; if the filing's
    body order disagrees with item-number order (rare but possible in
    amendments) we still respect the document layout, not the numbering.
    """
    last_by_item: dict[str, int] = {}
    for m in _ITEM_RE.finditer(text):
        item = _normalize_item_id(m.group("num"), m.group("sub"))
        if item not in ITEM_TITLES:
            continue
        last_by_item[item] = m.start()
    return sorted(((pos, item) for item, pos in last_by_item.items()))


def parse_sections(html: str) -> list[Section]:
    """Split a 10-K filing into Section objects.

    Returns sections in document order. Sections shorter than
    `_MIN_SECTION_CHARS` are dropped — they're almost always TOC noise that
    survived the last-occurrence heuristic (e.g. a filing that mentions
    "Item 15" only once, inside the TOC, because the exhibit list uses a
    different header style).
    """
    text = html_to_text(html)
    headers = _resolve_headers(text)
    if not headers:
        return []

    sections: list[Section] = []
    for i, (start, item) in enumerate(headers):
        end = headers[i + 1][0] if i + 1 < len(headers) else len(text)
        block = text[start:end]

        # Header line is the first line of the block; body is the rest.
        newline = block.find("\n")
        header_line = block[:newline].strip() if newline != -1 else block.strip()
        body = block[newline + 1 :].strip() if newline != -1 else ""

        if len(body) < _MIN_SECTION_CHARS:
            continue

        # Use the filing's header text after the item number if it looks
        # like a real title; otherwise fall back to the canonical title.
        title = _extract_title(header_line) or ITEM_TITLES[item]
        sections.append(
            Section(
                item=item,
                title=title,
                text=body,
                char_start=start,
                char_end=end,
            )
        )
    return sections


def _extract_title(header_line: str) -> str | None:
    """Pull the human title out of a header line like 'Item 1A. Risk Factors'."""
    m = re.match(
        r"(?i)^\s*item\s+\d{1,2}[A-C]?\s*[.—–:\-]?\s*(?P<title>.+?)\s*$",
        header_line,
    )
    if not m:
        return None
    title = m.group("title").strip(" .:-—–")
    return title or None
