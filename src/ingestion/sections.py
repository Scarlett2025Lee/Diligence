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

10-Q twist: a 10-Q has TWO parts whose item numbers collide (Part I Item 2
is MD&A; Part II Item 2 is Unregistered Sales). The plain last-occurrence
rule would keep only the Part II items and silently drop MD&A — the exact
section a "management outlook" question needs. So for 10-Qs we first locate
the PART I / PART II headings (same last-occurrence idea, anchored so the
TOC's part entries lose), then resolve items independently inside each
part's range and namespace the ids: "I.2", "II.1A".

This is heuristic, not a SEC-grade parser. It targets the modern HTML
filings (2001+) which dominate EDGAR. Edge cases (amendments, embedded
XBRL, exhibit-only filings) are out of scope for Phase 1.
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

# Canonical titles for 10-Q items, keyed by part-scoped id. Part I and
# Part II reuse item numbers, so the id carries the part: "I.2" is MD&A,
# "II.2" is buybacks. These ids flow into Chunk.item and the citation
# chips ("Item I.2") — compact and unambiguous.
ITEM_TITLES_10Q: dict[str, str] = {
    "I.1": "Financial Statements",
    "I.2": "Management's Discussion and Analysis",
    "I.3": "Quantitative and Qualitative Disclosures About Market Risk",
    "I.4": "Controls and Procedures",
    "II.1": "Legal Proceedings",
    "II.1A": "Risk Factors",
    "II.2": "Unregistered Sales of Equity Securities and Use of Proceeds",
    "II.3": "Defaults Upon Senior Securities",
    "II.4": "Mine Safety Disclosures",
    "II.5": "Other Information",
    "II.6": "Exhibits",
}

# Item header anywhere in the line. Tolerates Unicode dashes, optional period
# after the number, optional "Part" prefix on a prior line, and stray
# whitespace from HTML rendering. The trailing lookahead requires a space or
# punctuation so "Item 1ABC" doesn't match "Item 1A".
_ITEM_RE = re.compile(
    r"(?im)^\s*item\s+(?P<num>\d{1,2})(?P<sub>[A-C])?\s*[.—–:\-]?(?=\s|$)"
)

# PART I / PART II heading at line start. Roman numerals only — 10-Qs have
# exactly two parts, 10-Ks up to four, and we only branch on I/II here.
_PART_RE = re.compile(r"(?im)^\s*part\s+(?P<part>II|I)\b")

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

    # Force a newline after each block-level boundary. NB: tr is here,
    # td/th are NOT — separating every cell with a newline turned every
    # SEC table into one column per line. With cells left alone, the
    # default get_text(separator=" ") puts a single space between cells
    # and the tr-level newline ends the row. Output:
    #     Americas $ 178,353  7 %  $ 167,045  3 %  $ 162,560
    # instead of "Americas" / "$" / "178,353" / "7" / "%" each on its
    # own line.
    for tag in soup.find_all(
        ["p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"]
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


def _resolve_headers(
    text: str,
    *,
    start: int = 0,
    end: int | None = None,
    titles: dict[str, str] | None = None,
    id_prefix: str = "",
) -> list[tuple[int, str]]:
    """Return [(char_offset, item_id)] sorted by position, scanning
    text[start:end] only.

    For each distinct item id we keep only the LAST match — earlier matches
    are TOC entries. We then sort the survivors by offset; if the filing's
    body order disagrees with item-number order (rare but possible in
    amendments) we still respect the document layout, not the numbering.

    `titles` is the validity filter (which item numbers are real for this
    form/part); `id_prefix` namespaces the returned ids ("I." / "II.") so
    10-Q parts don't collide. Offsets are absolute into `text` and advanced
    past the leading whitespace the `^\\s*` part of the regex matches, so
    block = text[offset:] starts with "Item …" not a stray `\\n`.
    """
    end = len(text) if end is None else end
    titles = ITEM_TITLES if titles is None else titles
    last_by_item: dict[str, int] = {}
    for m in _ITEM_RE.finditer(text, start, end):
        item = id_prefix + _normalize_item_id(m.group("num"), m.group("sub"))
        if item not in titles:
            continue
        pos = m.start()
        while pos < len(text) and text[pos] in " \t\n":
            pos += 1
        last_by_item[item] = pos
    return sorted(((pos, item) for item, pos in last_by_item.items()))


def _resolve_part_ranges(text: str) -> list[tuple[str, int, int]]:
    """Locate the real PART I / PART II headings in a 10-Q.

    Returns [(part_label, start, end)] in document order. The real Part II
    heading is the LAST "PART II" match (TOC entries come earlier); the
    real Part I heading is the last "PART I" match BEFORE that point — a
    cross-reference like "Part I, Item 2" inside Part II body can't steal
    the boundary by construction.
    """
    part1_positions = []
    part2_positions = []
    for m in _PART_RE.finditer(text):
        (part2_positions if m.group("part").upper() == "II" else part1_positions).append(
            m.start()
        )
    if not part1_positions or not part2_positions:
        return []
    p2 = part2_positions[-1]
    p1_candidates = [p for p in part1_positions if p < p2]
    if not p1_candidates:
        return []
    p1 = p1_candidates[-1]
    return [("I", p1, p2), ("II", p2, len(text))]


def parse_sections(html: str, form: str = "10-K") -> list[Section]:
    """Split a filing into Section objects.

    `form` selects the header-resolution strategy: anything containing
    "10-Q" gets the two-part, namespaced treatment ("I.2", "II.1A");
    everything else uses the flat 10-K item space. Returns sections in
    document order. Sections shorter than `_MIN_SECTION_CHARS` are
    dropped — they're almost always TOC noise that survived the
    last-occurrence heuristic (e.g. a filing that mentions "Item 15" only
    once, inside the TOC, because the exhibit list uses a different header
    style).
    """
    text = html_to_text(html)
    is_10q = "10-Q" in form.upper()

    if is_10q:
        titles = ITEM_TITLES_10Q
        headers: list[tuple[int, str]] = []
        for label, p_start, p_end in _resolve_part_ranges(text):
            headers.extend(
                _resolve_headers(
                    text,
                    start=p_start,
                    end=p_end,
                    titles=titles,
                    id_prefix=f"{label}.",
                )
            )
        # Fall back to flat resolution if the part headings weren't found
        # (some older filings inline them oddly). Better a mislabeled
        # section than an empty parse.
        if not headers:
            headers = _resolve_headers(text, titles=ITEM_TITLES)
            titles = ITEM_TITLES
    else:
        titles = ITEM_TITLES
        headers = _resolve_headers(text, titles=titles)

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
        title = _extract_title(header_line) or titles[item]
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
