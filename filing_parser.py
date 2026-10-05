"""
filing_parser.py — Parse a 10-K/10-Q HTML document into structured sections.

Provides:
    FilingItem    — dataclass for one Item section
    ParsedFiling  — dataclass for the full filing
    parse_filing(meta: FilingMeta) -> ParsedFiling

Usage:
    python filing_parser.py  # demo with hard-coded URL
"""
from __future__ import annotations

import re
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

from filing_fetcher import FilingMeta, USER_AGENT

try:
    from html.parser import HTMLParser
except ImportError:
    raise

# ── Dollar / percent pattern helpers ───────────────────────────────────────────

_DOLLAR_RE = re.compile(r"\$[\d,]+(?:\.\d+)?\s*(?:million|billion|trillion|[BMT])?", re.I)
_PCT_RE = re.compile(r"\d+(?:\.\d+)?\s*%")
_ITEM_SPLIT_RE = re.compile(r"(?i)(?:^|\n)\s*item\s+(\d+[A-Za-z]?)[.\s—–\-]", re.M)


# ── HTML stripper ───────────────────────────────────────────────────────────────

class _HTMLStripper(HTMLParser):
    """Minimal HTML stripper using stdlib html.parser (no regex for HTML)."""

    SKIP_TAGS = {"script", "style", "head", "meta", "link"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.SKIP_TAGS:
            self._skip_depth += 1
        elif tag.lower() in {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "td"}:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag.lower() in self.SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        # Normalize whitespace
        lines = [" ".join(line.split()) for line in raw.splitlines()]
        lines = [l for l in lines if l]
        return "\n".join(lines)


def _strip_html(html_bytes: bytes) -> str:
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            html_str = html_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        html_str = html_bytes.decode("utf-8", errors="replace")

    stripper = _HTMLStripper()
    stripper.feed(html_str)
    return stripper.get_text()


# ── Dataclasses ─────────────────────────────────────────────────────────────────

@dataclass
class FilingItem:
    item_num: str
    title: str
    text: str
    word_count: int = 0
    sentence_count: int = 0
    dollar_mentions: int = 0
    pct_mentions: int = 0

    def __post_init__(self):
        if not self.word_count:
            self.word_count = len(self.text.split())
        if not self.sentence_count:
            self.sentence_count = len(re.split(r"[.!?]+", self.text))
        if not self.dollar_mentions:
            self.dollar_mentions = len(_DOLLAR_RE.findall(self.text))
        if not self.pct_mentions:
            self.pct_mentions = len(_PCT_RE.findall(self.text))


@dataclass
class ParsedFiling:
    ticker: str
    form_type: str
    filed_date: str
    accession: str
    fiscal_year_end: str
    items: list[FilingItem] = field(default_factory=list)

    def get_item(self, num: str) -> Optional[FilingItem]:
        """Return FilingItem for the given item number, or None."""
        num = num.upper().strip()
        for item in self.items:
            if item.item_num.upper() == num:
                return item
        return None


# ── Parser ──────────────────────────────────────────────────────────────────────

def _fetch_html(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()
    time.sleep(0.1)


def _extract_fiscal_year_end(text: str) -> str:
    """Best-effort extraction of fiscal year end date."""
    patterns = [
        r"fiscal year ended?\s+([A-Za-z]+ \d+,\s*\d{4})",
        r"year ended?\s+([A-Za-z]+ \d+,\s*\d{4})",
        r"period ended?\s+([A-Za-z]+ \d+,\s*\d{4})",
    ]
    for pat in patterns:
        m = re.search(pat, text[:5000], re.I)
        if m:
            return m.group(1).strip()
    return ""


def _split_into_items(text: str) -> list[tuple[str, str, str]]:
    """Split text into list of (item_num, header_text, body_text)."""
    matches = list(_ITEM_SPLIT_RE.finditer(text))
    if not matches:
        return [("0", "Full Document", text)]

    results = []
    for i, match in enumerate(matches):
        item_num = match.group(1).upper()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        # Try to extract a title from the first line
        first_line = body.split("\n")[0].strip()[:200] if body else ""
        title = first_line if first_line else f"Item {item_num}"
        results.append((item_num, title, body))

    return results


def parse_filing(meta: FilingMeta) -> ParsedFiling:
    """Download and parse a filing into a ParsedFiling."""
    html_bytes = _fetch_html(meta.doc_url)
    text = _strip_html(html_bytes)
    fiscal_year_end = _extract_fiscal_year_end(text)

    raw_items = _split_into_items(text)
    items = [
        FilingItem(
            item_num=num,
            title=title,
            text=body,
        )
        for num, title, body in raw_items
        if body.strip()
    ]

    return ParsedFiling(
        ticker=meta.ticker,
        form_type=meta.form_type,
        filed_date=meta.filed_date,
        accession=meta.accession,
        fiscal_year_end=fiscal_year_end,
        items=items,
    )


if __name__ == "__main__":
    # Demo: parse a known EDGAR filing index page
    from filing_fetcher import FilingFetcher
    print("Demo: parsing AAPL 10-K...")
    fetcher = FilingFetcher()
    old, new = fetcher.get_two_most_recent("AAPL", "10-K")
    parsed = parse_filing(new)
    print(f"  Ticker       : {parsed.ticker}")
    print(f"  Form         : {parsed.form_type}")
    print(f"  Filed        : {parsed.filed_date}")
    print(f"  Fiscal YE    : {parsed.fiscal_year_end}")
    print(f"  Items found  : {len(parsed.items)}")
    for item in parsed.items[:5]:
        print(f"    Item {item.item_num}: {item.word_count} words, "
              f"{item.dollar_mentions} $ mentions")
