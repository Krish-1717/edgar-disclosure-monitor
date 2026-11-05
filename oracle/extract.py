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

import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# Inline XBRL filings are XHTML with an <?xml?> prolog; the HTML parser is what we want.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# (part, item) -> (key, title).  part=None means "any part" (10-K items are unique).
TARGETS_10K = {
    (None, "1A"): ("risk_factors", "Risk Factors"),
    (None, "7"): ("mdna", "Management's Discussion and Analysis"),
    (None, "7A"): ("market_risk", "Quantitative and Qualitative Disclosures About Market Risk"),
    (None, "8"): ("financial_statements", "Financial Statements and Supplementary Data"),
    # Many filers (e.g. NVIDIA) put only a cross-reference under Item 8 and print the
    # statements under Item 15; used as a fallback for financial_statements.
    (None, "15"): ("_item15", "Exhibits and Financial Statement Schedules"),
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
_SPACE_RE = re.compile(r"[ \t\u00a0\u2002\u2003\u2009\u200a\u200b\u202f\ufeff]+")
_ITEM_RE = re.compile(
    r"^\s*item[\s\u00a0]*(\d{1,2}[a-c]?)\s*[.:\-\u2013\u2014]?\s*(.{0,160})$",
    re.IGNORECASE | re.MULTILINE,
)
_PART_RE = re.compile(r"^\s*part[\s\u00a0]+(iv|iii|ii|i|[1-4])\b[^\n]{0,120}$", re.IGNORECASE | re.MULTILINE)
_ROMAN = {"1": "I", "2": "II", "3": "III", "4": "IV"}
MIN_SECTION_CHARS = 60    # short "no material changes" statements are still useful


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


def _part_markers(text: str) -> list[tuple[int, str]]:
    """PART markers where the part changes (running page headers repeat the current part)."""
    out: list[tuple[int, str]] = []
    for m in _PART_RE.finditer(text):
        part = _ROMAN.get(m.group(1).upper(), m.group(1).upper())
        if not out or out[-1][1] != part:
            out.append((m.start(), part))
    return out


# 10-Q item titles are standardised (Form 10-Q General Instructions), so the title tells
# the part even when PART headings are missing or a second table of contents misleads.
_TITLE_PART = [
    (re.compile(r"financial statements", re.I), {"1": "I"}),
    (re.compile(r"management.{0,3}s discussion|discussion and analysis", re.I), {"2": "I"}),
    (re.compile(r"quantitative and qualitative|market risk", re.I), {"3": "I"}),
    (re.compile(r"controls and procedures", re.I), {"4": "I"}),
    (re.compile(r"legal proceedings", re.I), {"1": "II"}),
    (re.compile(r"risk factors", re.I), {"1A": "II"}),
    (re.compile(r"unregistered sales|equity securities|use of proceeds", re.I), {"2": "II"}),
    (re.compile(r"defaults upon senior", re.I), {"3": "II"}),
    (re.compile(r"mine safety", re.I), {"4": "II"}),
]


def _part_from_title(item: str, title: str) -> str | None:
    for rx, mapping in _TITLE_PART:
        if item in mapping and rx.search(title):
            return mapping[item]
    return None


def _headings(text: str, parts: list[tuple[int, str]]) -> list[_Heading]:
    heads: list[_Heading] = []
    for m in _ITEM_RE.finditer(text):
        part = None
        for pos, p in parts:
            if pos <= m.start():
                part = p
            else:
                break
        item = m.group(1).upper()
        part = _part_from_title(item, m.group(2) or "") or part
        # Running page headers ("PART II / Item 7" on every page) repeat the open item.
        if heads and (heads[-1].part, heads[-1].item) == (part, item):
            continue
        heads.append(_Heading(m.start(), m.end(), part, item))
    return heads


_RUNNING_HEADER_RE = re.compile(r"^(?:part [iv]+|item \d{1,2}[a-c]?|\d{1,3}|page \d{1,3})$", re.IGNORECASE)


def _clean_body(body: str) -> str:
    lines = [ln for ln in body.split("\n") if not _RUNNING_HEADER_RE.match(ln.strip())]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def segment(text: str, form: str) -> list[dict]:
    """Return [{key, item, title, text}] for the target items found in ``text``."""
    base = form.upper().replace("/A", "")
    if base.startswith("10-K"):
        targets, use_part = TARGETS_10K, False
    elif base.startswith("10-Q"):
        targets, use_part = TARGETS_10Q, True
    else:
        return []

    parts = _part_markers(text)
    heads = _headings(text, parts)
    part_starts = [pos for pos, _ in parts]
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
        body = _clean_body(text[h.body_start:end])
        label = f"Part {h.part}, Item {h.item}" if use_part else f"Item {h.item}"
        if len(body) > best.get(key, (0,))[0]:
            best[key] = (len(body), label, title, body)

    item15 = best.pop("_item15", None)
    fs = best.get("financial_statements")
    if item15 and (fs is None or fs[0] < 1000) and item15[0] > (fs[0] if fs else 0):
        best["financial_statements"] = (item15[0], "Item 15 (referenced from Item 8)",
                                        "Financial Statements and Supplementary Data", item15[3])

    order = [v[0] for v in targets.values() if not v[0].startswith("_")]
    return [
        {"key": k, "item": best[k][1], "title": best[k][2], "text": best[k][3]}
        for k in order if k in best and best[k][0] >= MIN_SECTION_CHARS
    ]


def segment_html(html: bytes | str, form: str) -> list[dict]:
    return segment(html_to_text(html), form)
