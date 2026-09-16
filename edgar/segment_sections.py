"""
segment_sections.py — Split clean filing text into labeled SEC form sections.

Day 3: Reads clean_text from the documents table and produces one row per
section in the sections table.

Schema:
    sections(id, filing_id, item_key, item_label, body_text)

10-K items recognised (Item 1 through 15, common subset):
    1   Business
    1A  Risk Factors
    1B  Unresolved Staff Comments
    1C  Cybersecurity
    2   Properties
    3   Legal Proceedings
    4   Mine Safety Disclosures
    5   Market for Registrant Common Equity
    6   Reserved  (formerly Selected Financial Data)
    7   Management Discussion and Analysis
    7A  Quantitative and Qualitative Disclosures About Market Risk
    8   Financial Statements and Supplementary Data
    9   Changes in and Disagreements with Accountants
    9A  Controls and Procedures
    9B  Other Information
    9C  Disclosure re Foreign Jurisdictions
    10  Directors, Executive Officers and Corporate Governance
    11  Executive Compensation
    12  Security Ownership
    13  Certain Relationships
    14  Principal Accountant Fees and Services
    15  Exhibits and Financial Statement Schedules

10-Q items recognised:
    Part I, Item 1  Financial Statements
    Part I, Item 2  MD&A
    Part I, Item 3  Quantitative and Qualitative Disclosures
    Part I, Item 4  Controls and Procedures
    Part II, Item 1  Legal Proceedings
    Part II, Item 1A Risk Factors
    Part II, Item 2  Unregistered Sales
    Part II, Item 3  Defaults
    Part II, Item 4  Mine Safety
    Part II, Item 5  Other Information
    Part II, Item 6  Exhibits

Approach:
  - Regex-based boundary detection on lines that look like section headers.
  - Headers are identified by patterns like "Item 1." or "ITEM 1A." or
    "Item 1.\tBusiness" with flexible whitespace and optional periods.
  - The body of each section is everything between two consecutive headers.
  - Short sections (<20 words) are flagged but retained.

Run modes:
  python -m edgar.segment_sections                        # all pending
  python -m edgar.segment_sections --ticker AAPL          # one company
  python -m edgar.segment_sections --filing_id 42         # one filing
  python -m edgar.segment_sections --dry_run              # print, no write
"""

import re
import sqlite3
import argparse
from pathlib import Path
from dataclasses import dataclass

# ── Section catalogue ─────────────────────────────────────────────────────────

# Maps normalised item key (e.g. "1A", "7") to a human label.
ITEMS_10K: dict[str, str] = {
    "1":   "Business",
    "1A":  "Risk Factors",
    "1B":  "Unresolved Staff Comments",
    "1C":  "Cybersecurity",
    "2":   "Properties",
    "3":   "Legal Proceedings",
    "4":   "Mine Safety Disclosures",
    "5":   "Market for Registrant Common Equity",
    "6":   "Reserved",
    "7":   "Management Discussion and Analysis",
    "7A":  "Quantitative and Qualitative Disclosures About Market Risk",
    "8":   "Financial Statements and Supplementary Data",
    "9":   "Changes in and Disagreements with Accountants",
    "9A":  "Controls and Procedures",
    "9B":  "Other Information",
    "9C":  "Disclosure Regarding Foreign Jurisdictions",
    "10":  "Directors, Executive Officers and Corporate Governance",
    "11":  "Executive Compensation",
    "12":  "Security Ownership of Certain Beneficial Owners",
    "13":  "Certain Relationships and Related Transactions",
    "14":  "Principal Accountant Fees and Services",
    "15":  "Exhibits and Financial Statement Schedules",
}

ITEMS_10Q: dict[str, str] = {
    "P1I1":  "Financial Statements",
    "P1I2":  "Management Discussion and Analysis",
    "P1I3":  "Quantitative and Qualitative Disclosures About Market Risk",
    "P1I4":  "Controls and Procedures",
    "P2I1":  "Legal Proceedings",
    "P2I1A": "Risk Factors",
    "P2I2":  "Unregistered Sales of Equity Securities",
    "P2I3":  "Defaults Upon Senior Securities",
    "P2I4":  "Mine Safety Disclosures",
    "P2I5":  "Other Information",
    "P2I6":  "Exhibits",
}

# ── Regex patterns ────────────────────────────────────────────────────────────

# Matches "Item 1.", "ITEM 1A.", "Item 7A", etc. at the start of a line.
# Group 1 = item number (e.g. "1A", "7")
_10K_HEADER_RE = re.compile(
    r"^\s*ITEM\s+(\d{1,2}[A-C]?)[\.\s]",
    re.IGNORECASE | re.MULTILINE,
)

# 10-Q Part / Item pattern
# Matches "Part I, Item 2" or "PART II – ITEM 1A"
_10Q_HEADER_RE = re.compile(
    r"^\s*PART\s+(I{1,3}|IV|V)\s*[,\-–—]?\s*ITEM\s+(\d{1,2}[A-C]?)",
    re.IGNORECASE | re.MULTILINE,
)

_ROMAN_TO_INT = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class Section:
    item_key:   str   # e.g. "1A" for 10-K, "P2I1A" for 10-Q
    item_label: str   # human label
    body_text:  str   # section body


# ── Segmentation logic ────────────────────────────────────────────────────────

def _normalise_item(raw: str) -> str:
    """Upper-case and strip trailing dots from a raw item token."""
    return raw.upper().strip(".")


def segment_10k(text: str) -> list[Section]:
    """
    Extract sections from a 10-K clean_text.
    Returns a list of Section objects in document order.
    """
    matches = list(_10K_HEADER_RE.finditer(text))
    if not matches:
        return []

    sections = []
    for idx, m in enumerate(matches):
        raw_key = _normalise_item(m.group(1))
        label = ITEMS_10K.get(raw_key, f"Item {raw_key}")
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections.append(Section(item_key=raw_key, item_label=label, body_text=body))

    return sections


def segment_10q(text: str) -> list[Section]:
    """
    Extract sections from a 10-Q clean_text.
    Returns a list of Section objects in document order.
    """
    matches = list(_10Q_HEADER_RE.finditer(text))
    if not matches:
        return []

    sections = []
    for idx, m in enumerate(matches):
        roman = m.group(1).upper()
        part_num = _ROMAN_TO_INT.get(roman, 1)
        item_raw = _normalise_item(m.group(2))
        key = f"P{part_num}I{item_raw}"
        label = ITEMS_10Q.get(key, f"Part {roman} Item {item_raw}")
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections.append(Section(item_key=key, item_label=label, body_text=body))

    return sections


def segment_filing(text: str, form_type: str) -> list[Section]:
    """
    Dispatch to the right segmenter based on form_type.
    form_type: "10-K" or "10-Q" (case-insensitive prefix match).
    """
    ft = form_type.upper().replace("/A", "").strip()
    if ft.startswith("10-K"):
        return segment_10k(text)
    elif ft.startswith("10-Q"):
        return segment_10q(text)
    else:
        return []  # unsupported form type


# ── DB helpers ────────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).parent.parent / "edgar_monitor.db"
SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def _open_db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SCHEMA_PATH.read_text())
    return con


def _pending_documents(
    con: sqlite3.Connection,
    ticker: str | None = None,
    filing_id: int | None = None,
) -> list:
    """Documents that have a clean_text but no sections yet."""
    base = """
        SELECT d.filing_id, d.clean_text, f.form_type, f.ticker, f.filing_date
        FROM documents d
        JOIN filings f ON f.id = d.filing_id
        LEFT JOIN sections s ON s.filing_id = d.filing_id
        WHERE s.id IS NULL
          AND d.clean_text IS NOT NULL
          AND length(d.clean_text) > 100
    """
    if filing_id:
        return con.execute(base + " AND d.filing_id = ?", (filing_id,)).fetchall()
    if ticker:
        return con.execute(base + " AND f.ticker = ?", (ticker.upper(),)).fetchall()
    return con.execute(base).fetchall()


def _insert_sections(con: sqlite3.Connection, filing_id: int, sections: list[Section]) -> int:
    inserted = 0
    for sec in sections:
        con.execute(
            """
            INSERT OR IGNORE INTO sections (filing_id, item_key, item_label, body_text)
            VALUES (?, ?, ?, ?)
            """,
            (filing_id, sec.item_key, sec.item_label, sec.body_text),
        )
        inserted += 1
    con.commit()
    return inserted


# ── Main runner ───────────────────────────────────────────────────────────────

def segment_all(
    ticker: str | None = None,
    filing_id: int | None = None,
    dry_run: bool = False,
) -> None:
    con = _open_db()
    pending = _pending_documents(con, ticker, filing_id)
    total = len(pending)
    print(f"Documents to segment: {total}")
    if not total:
        print("Nothing to do.")
        return

    ok = err = skip = 0
    for i, row in enumerate(pending, 1):
        fid = row["filing_id"]
        ft = row["form_type"]
        t = row["ticker"]
        dt = row["filing_date"]
        text = row["clean_text"] or ""

        sections = segment_filing(text, ft)
        n = len(sections)
        print(f"[{i}/{total}] {t} {ft} {dt} — {n} sections found")

        if n == 0:
            skip += 1
            continue

        if dry_run:
            for s in sections:
                words = len(s.body_text.split())
                print(f"  {s.item_key:6s}  {s.item_label[:40]:40s}  {words:>6} words")
            skip += 1
            continue

        try:
            ins = _insert_sections(con, fid, sections)
            ok += 1
        except Exception as exc:
            print(f"  DB error: {exc}")
            err += 1

    con.close()
    print(f"\nDone. ok={ok}  skip={skip}  err={err}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Segment filing clean_text into labelled SEC sections."
    )
    p.add_argument("--ticker",     help="Process only this ticker")
    p.add_argument("--filing_id",  type=int, help="Process one filing by ID")
    p.add_argument("--dry_run",    action="store_true", help="Print only, no DB writes")
    args = p.parse_args()
    segment_all(ticker=args.ticker, filing_id=args.filing_id, dry_run=args.dry_run)
