"""
parse_html.py — Strip EDGAR HTML filings to clean text, extract tables.

Day 2: Converts raw HTML from EDGAR into:
  - clean_text : normalized body text, ready for section segmentation
  - table_json : tables extracted separately as JSON rows

Rules:
  - Tables are removed from clean_text and stored in table_json.
    They contain financial figures that destroy paragraph diffs.
  - Page numbers, TOC entries, headers/footers are stripped.
  - Whitespace is normalised: multiple spaces → single space,
    multiple blank lines → single blank line.
  - Unicode smart quotes, dashes, and non-breaking spaces are normalised.

Usage:
    from edgar.parse_html import parse_filing_html
    clean_text, table_json = parse_filing_html(raw_html)
"""

import re
import json
import unicodedata
from typing import Tuple, List, Dict

try:
    from bs4 import BeautifulSoup, Comment
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# ── Table extraction ───────────────────────────────────────────────────────────

def _extract_tables(soup) -> List[Dict]:
    """
    Extract all tables from the soup as a list of row-lists.
    Modifies soup in-place: removes table tags after extraction.
    Returns a list of {"headers": [...], "rows": [[...], ...]} dicts.
    """
    tables = []
    for table in soup.find_all("table"):
        rows = []
        headers = []
        first_row = True
        for tr in table.find_all("tr"):
            cells = [td.get_text(separator=" ", strip=True)
                     for td in tr.find_all(["td", "th"])]
            if not any(cells):
                continue
            if first_row:
                headers = cells
                first_row = False
            else:
                rows.append(cells)
        if rows or headers:
            tables.append({"headers": headers, "rows": rows})
        table.decompose()  # remove from DOM so it doesn't appear in clean_text
    return tables


# ── Boilerplate strip ─────────────────────────────────────────────────────────

# Patterns that identify boilerplate lines to discard
_PAGE_NUM_RE   = re.compile(r"^\s*-?\s*\d{1,4}\s*-?\s*$")
_TOC_LINE_RE   = re.compile(r"^.*\.{4,}\s*\d{1,4}\s*$")   # "Item 1A .... 23"
_RULE_LINE_RE  = re.compile(r"^[_\-=]{5,}\s*$")              # horizontal rules


def _is_boilerplate(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if _PAGE_NUM_RE.match(s):
        return True
    if _TOC_LINE_RE.match(s):
        return True
    if _RULE_LINE_RE.match(s):
        return True
    return False


# ── Unicode normalisation ─────────────────────────────────────────────────────

_UNICODE_MAP = str.maketrans({
    "\u2018": "'",   # left single quote
    "\u2019": "'",   # right single quote
    "\u201c": '"',   # left double quote
    "\u201d": '"',   # right double quote
    "\u2013": "-",   # en-dash
    "\u2014": "-",   # em-dash
    "\u00a0": " ",   # non-breaking space
    "\u2022": "*",   # bullet
    "\u00ae": "(R)",
    "\u00a9": "(c)",
})


def _normalise_unicode(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_UNICODE_MAP)
    return text


# ── Main parser ───────────────────────────────────────────────────────────────

def parse_filing_html(raw_html: str) -> Tuple[str, str]:
    """
    Parse a raw EDGAR HTML filing.

    Returns
    -------
    clean_text : str
        Normalised body text with tables removed.
    table_json : str
        JSON string — list of extracted table dicts.
    """
    if not HAS_BS4:
        raise ImportError(
            "beautifulsoup4 and lxml are required. "
            "Run: pip install beautifulsoup4 lxml"
        )

    # --- Parse HTML ---
    soup = BeautifulSoup(raw_html, "lxml")

    # Remove HTML comments
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Remove script, style, meta, link tags
    for tag in soup.find_all(["script", "style", "meta", "link", "head"]):
        tag.decompose()

    # --- Extract tables (modifies soup in-place) ---
    tables = _extract_tables(soup)

    # --- Get text ---
    # Use newline as block separator for block-level elements
    for tag in soup.find_all(["p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4"]):
        tag.insert_after("\n")

    raw_text = soup.get_text(separator=" ")

    # --- Unicode normalise ---
    raw_text = _normalise_unicode(raw_text)

    # --- Line-level cleanup ---
    lines = raw_text.splitlines()
    clean_lines = []
    for line in lines:
        # Collapse internal whitespace
        line = re.sub(r"[ \t]+", " ", line).strip()
        if _is_boilerplate(line):
            continue
        clean_lines.append(line)

    # Collapse runs of more than 2 blank lines → 1
    text = "\n".join(clean_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strip leading/trailing whitespace
    clean_text = text.strip()

    table_json = json.dumps(tables, ensure_ascii=False)
    return clean_text, table_json


# ── Plain-text fallback (for .txt filings) ────────────────────────────────────

def parse_filing_txt(raw_txt: str) -> Tuple[str, str]:
    """
    Minimal normalisation for .txt (not HTML) filings.
    Tables are not extracted separately.
    """
    text = _normalise_unicode(raw_txt)
    lines = text.splitlines()
    clean_lines = []
    for line in lines:
        line = re.sub(r"[ \t]+", " ", line).strip()
        if _is_boilerplate(line):
            continue
        clean_lines.append(line)

    text = "\n".join(clean_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(), "[]"


# ── CLI smoke test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python parse_html.py <filing.html>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
        raw = f.read()

    clean, tables = parse_filing_html(raw)
    print(f"Clean text: {len(clean):,} chars")
    tbls = json.loads(tables)
    print(f"Tables extracted: {len(tbls)}")
    print("\nFirst 500 chars of clean text:")
    print(clean[:500])
