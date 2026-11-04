"""Minimal extraction: HTML -> text, then 10-K / 10-Q section segmentation.

Targets
  10-K: Item 1A (risk factors), Item 7 (MD&A), Item 7A (market risk), Item 8 (financial statements)
  10-Q: Part I Item 1 (financial statements), Part I Item 2 (MD&A),
        Part I Item 3 (market risk), Part II Item 1A (risk factors)

Every section gets a canonical ``key`` so both forms read the same way in the API.
Table-of-contents entries are suppressed by keeping, per item, the heading
occurrence followed by the most body text before the next item heading.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

# (part, item) -> (key, title).  part=None means "any part" (10-K items are unique).
TARGETS_10K = {
    (None, "1A"): ("risk_factors", "Risk Factors"),
    (None, "7"): ("mdna", "Management's Discussion and Analysis"),
    (None, "7A"): ("market_risk", "Quantitative and Qualitative Disclosures About Market Risk"),
    (None, "8"): ("financial_statements", "Financial Statements and Supplementary Data"),
}
TARGETS_10Q = {
    ("I", "1"): ("financial_statements", "Financial Statements"),
    ("I", "2"): ("mdna", "Management's Discussion and Analysis"),
    ("I", "3"): ("market_risk", "Quantitative and Qualitative Disclosures About Market Risk"),
    ("II", "1A"): ("risk_factors", "Risk Factors"),
}

_BLOCK_TAGS = [
    "p", "div", "tr", "li", "ul", "ol", "table", "section", "article", "blockquote", "pre",
    "h1", "h2", "h3", "h4", "h5", "h6", "title", "center",
]
_SPACE_RE = re.compile(r"[ \t     ​ ﻿]+")
_ITEM_RE = re.compile(
    r"^\s*item[\s ]*(\d{1,2}[a-c]?)\s*[.:\-–—]?\s*(.{0,160})$",
    re.IGNORECASE | re.MULTILINE,
)
_PART_RE = re.compile(r"^\s*part[\s ]+(iv|iii|ii|i|[1-4])\b[^\n]{0,120}$", re.IGNORECASE | re.MULTILINE)
_ROMAN = {"1": "I", "2": "II", "3": "III", "4": "IV"}
MIN_SECTION_CHARS = 200


def html_to_text(html: bytes | str) -> str:
    """Block-aware text extraction (inline spans are joined, blocks become lines)."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "head", "ix:header", "noscript"]):
        tag.decompose()
    for tag in soup.find_all(style=re.compile(r"display\s*:\s*none", re.I)):
        tag.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for cell in soup.find_all(["td", "th"]):
        cell.append(" ")
    for tag in soup.find_all(_BLOCK_TAGS):
        tag.insert_before("\n")
        tag.append("\n")
    text = soup.get_text()
    lines = (_SPACE_RE.sub(" ", line).strip() for line in text.splitlines())
    out: list[str] = []
    blank = False
    for line in lines:
        if line:
            out.append(line)
            blank = False
        elif not blank and out:
            out.append("")
            blank = True
    return "\n".join(out).strip()


@dataclass
class _Heading:
    start: int        # offset of heading line
    body_start: int   # offset just after heading line
    part: str | None
    item: str


def _headings(text: str) -> list[_Heading]:
    parts = [(m.start(), _ROMAN.get(m.group(1).upper(), m.group(1).upper())) for m in _PART_RE.finditer(text)]
    heads = []
    for m in _ITEM_RE.finditer(text):
        part = None
        for pos, p in parts:
            if pos <= m.start():
                part = p
            else:
                break
        heads.append(_Heading(m.start(), m.end(), part, m.group(1).upper()))
    return heads


def segment(text: str, form: str) -> list[dict]:
    """Return [{key, item, title, text}] for the target items found in ``text``."""
    base = form.upper().replace("/A", "")
    if base.startswith("10-K"):
        targets, use_part = TARGETS_10K, False
    elif base.startswith("10-Q"):
        targets, use_part = TARGETS_10Q, True
    else:
        return []

    heads = _headings(text)
    part_starts = sorted(m.start() for m in _PART_RE.finditer(text))
    best: dict[str, tuple[int, str, str, str]] = {}   # key -> (length, item_label, title, body)
    for i, h in enumerate(heads):
        target = targets.get((h.part if use_part else None, h.item))
        if not target:
            continue
        key, title = target
        end = heads[i + 1].start if i + 1 < len(heads) else len(text)
        # A "PART II" heading also ends the last item of Part I.
        nxt_part = next((p for p in part_starts if h.body_start <= p < end), None)
        if nxt_part is not None:
            end = nxt_part
        body = text[h.body_start:end].strip()
        label = f"Part {h.part}, Item {h.item}" if use_part else f"Item {h.item}"
        if len(body) > best.get(key, (0,))[0]:
            best[key] = (len(body), label, title, body)

    order = [v[0] for v in targets.values()]
    return [
        {"key": k, "item": best[k][1], "title": best[k][2], "text": best[k][3]}
        for k in order if k in best and best[k][0] >= MIN_SECTION_CHARS
    ]


def segment_html(html: bytes | str, form: str) -> list[dict]:
    return segment(html_to_text(html), form)
