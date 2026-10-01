"""
section_segmenter.py — 10-K/10-Q Section Extractor
Segments an SEC filing into Item-level sections by matching Item headings.
Handles common formatting variants: "ITEM 1A.", "Item 1A —", bold/anchor tags.
Target: ≥85% section accuracy on diverse filers.
"""
from __future__ import annotations
import re
import pathlib
import logging
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# Items we care about for 10-K
ITEMS_10K = {
    "1":   "Business",
    "1A":  "Risk Factors",
    "1B":  "Unresolved Staff Comments",
    "2":   "Properties",
    "3":   "Legal Proceedings",
    "5":   "Market for Registrant's Common Equity",
    "7":   "Management's Discussion and Analysis",
    "7A":  "Quantitative and Qualitative Disclosures About Market Risk",
    "8":   "Financial Statements",
    "9A":  "Controls and Procedures",
}

# Items for 10-Q (subset)
ITEMS_10Q = {
    "1":   "Financial Statements",
    "2":   "Management's Discussion and Analysis",
    "3":   "Quantitative and Qualitative Disclosures About Market Risk",
    "4":   "Controls and Procedures",
}

# Regex: matches "Item 1A", "ITEM 1A.", "Item 1A —", "ITEM 1A -"
_ITEM_RE = re.compile(
    r"(?:^|\n)\s*(?:ITEM|Item)\s+(\d{1,2}[A-C]?)\s*[.\-–—:]?\s*(.{0,80})?",
    re.IGNORECASE | re.MULTILINE,
)

# Pattern to clean up excessive whitespace and page artefacts
_CLEAN_RE = re.compile(r"\n{3,}")
_PAGE_NUM_RE = re.compile(r"^\s*\d+\s*$", re.MULTILINE)


def html_to_clean_text(html: str) -> str:
    """Strip HTML to clean plain text; move tables to side store placeholder."""
    soup = BeautifulSoup(html, "lxml")

    # Remove script/style/meta
    for tag in soup(["script", "style", "meta", "head"]):
        tag.decompose()

    # Replace table with placeholder so they don't break paragraph detection
    for table in soup.find_all("table"):
        table.replace_with(soup.new_string("\n[TABLE]\n"))

    text = soup.get_text(separator="\n")
    text = _PAGE_NUM_RE.sub("", text)
    text = _CLEAN_RE.sub("\n\n", text)
    return text.strip()


def segment_sections(text: str, form_type: str = "10-K") -> dict[str, str]:
    """
    Parse text into {item_number: section_text} dict.
    Uses table-of-contents suppression: prefer the occurrence with
    the most following text before the next heading.
    """
    item_map = ITEMS_10K if "10-K" in form_type else ITEMS_10Q
    target_items = set(item_map.keys())

    matches = list(_ITEM_RE.finditer(text))

    # Collect all candidate positions per item
    candidates: dict[str, list[tuple[int, int]]] = {}  # item -> [(start, end_next)]
    for i, m in enumerate(matches):
        item_num = m.group(1).upper().strip()
        if item_num not in target_items:
            continue
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        candidates.setdefault(item_num, []).append((start, end))

    # Pick the candidate with the most body text (suppresses TOC entries)
    sections: dict[str, str] = {}
    for item_num, locs in candidates.items():
        best_start, best_end = max(locs, key=lambda x: x[1] - x[0])
        body = text[best_start:best_end].strip()
        # Strip the heading line itself
        lines = body.split("\n")
        body = "\n".join(lines[1:]).strip()
        if len(body) > 100:  # ignore near-empty sections
            sections[item_num] = body

    missing = target_items - set(sections.keys())
    if missing:
        log.debug("Missing items: %s", sorted(missing))

    return sections


def split_paragraphs(text: str, min_words: int = 15) -> list[str]:
    """Split section text into paragraphs, filtering short fragments."""
    raw = re.split(r"\n{2,}", text)
    return [p.strip() for p in raw if len(p.split()) >= min_words]


def save_clean_text(text: str, path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_clean_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")
