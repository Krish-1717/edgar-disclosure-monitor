"""
fetch_documents.py — Download primary HTML documents for each filing.

Day 2: For every row in the filings table that doesn't yet have a documents
row, this module:
  1. Fetches the primary HTML document from EDGAR (using EdgarClient).
  2. Calls parse_html.parse_filing_html() to get clean_text + table_json.
  3. Inserts a row into the documents table.

Schema (from db/schema.sql):
    documents(filing_id INTEGER PRIMARY KEY,
              raw_html   TEXT,
              clean_text TEXT,
              table_json TEXT)

Run modes:
  python -m edgar.fetch_documents                 # all pending filings
  python -m edgar.fetch_documents --limit 50      # process at most N filings
  python -m edgar.fetch_documents --ticker AAPL   # one company only
  python -m edgar.fetch_documents --dry_run       # print URLs, no writes
"""

import sqlite3
import sys
import argparse
import time
import traceback
from pathlib import Path

from edgar.client import EdgarClient
from edgar.parse_html import parse_filing_html, parse_filing_txt

# ── DB helpers ─────────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).parent.parent / "edgar_monitor.db"
SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def _open_db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    # Apply schema if tables don't exist yet
    schema = SCHEMA_PATH.read_text()
    con.executescript(schema)
    return con


def _pending_filings(con: sqlite3.Connection, ticker: str | None = None) -> list:
    """
    Return filings that have no documents row yet.
    Optionally filter by ticker.
    """
    if ticker:
        rows = con.execute(
            """
            SELECT f.id, f.ticker, f.form_type, f.filing_date,
                   f.primary_doc_url, f.accession
            FROM filings f
            LEFT JOIN documents d ON d.filing_id = f.id
            WHERE d.filing_id IS NULL
              AND f.ticker = ?
            ORDER BY f.filing_date DESC
            """,
            (ticker.upper(),),
        ).fetchall()
    else:
        rows = con.execute(
            """
            SELECT f.id, f.ticker, f.form_type, f.filing_date,
                   f.primary_doc_url, f.accession
            FROM filings f
            LEFT JOIN documents d ON d.filing_id = f.id
            WHERE d.filing_id IS NULL
            ORDER BY f.filing_date DESC
            """,
        ).fetchall()
    return rows


def _insert_document(
    con: sqlite3.Connection,
    filing_id: int,
    raw_html: str,
    clean_text: str,
    table_json: str,
) -> None:
    con.execute(
        """
        INSERT OR IGNORE INTO documents (filing_id, raw_html, clean_text, table_json)
        VALUES (?, ?, ?, ?)
        """,
        (filing_id, raw_html, clean_text, table_json),
    )
    con.commit()


# ── Fetch logic ────────────────────────────────────────────────────────────────

def _fetch_one(
    client: EdgarClient,
    filing_id: int,
    url: str,
    dry_run: bool = False,
) -> tuple[str, str, str] | None:
    """
    Download + parse one document URL.
    Returns (raw_html, clean_text, table_json) or None on error.
    """
    if dry_run:
        print(f"  [dry_run] would fetch {url}")
        return None

    try:
        raw = client.get_html(url)
    except Exception as exc:
        print(f"  ERROR fetching {url}: {exc}")
        return None

    # Detect plain-text EDGAR filings (some older filings are .txt)
    if url.lower().endswith(".txt") and not raw.lstrip().startswith("<"):
        clean_text, table_json = parse_filing_txt(raw)
    else:
        try:
            clean_text, table_json = parse_filing_html(raw)
        except Exception as exc:
            print(f"  WARN parse error for filing_id={filing_id}: {exc}")
            clean_text, table_json = raw[:5_000_000], "[]"

    return raw, clean_text, table_json


# ── Main runner ────────────────────────────────────────────────────────────────

def fetch_documents(
    ticker: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> None:
    con = _open_db()
    client = EdgarClient()

    pending = _pending_filings(con, ticker)
    if limit:
        pending = pending[:limit]

    total = len(pending)
    print(f"Pending filings to process: {total}")
    if total == 0:
        print("Nothing to do.")
        return

    ok = 0
    skip = 0
    err = 0

    for i, row in enumerate(pending, 1):
        filing_id = row["id"]
        url = row["primary_doc_url"]
        ticker_str = row["ticker"]
        form_type = row["form_type"]
        date_str = row["filing_date"]

        if not url:
            print(f"[{i}/{total}] {ticker_str} {form_type} {date_str} — no URL, skipping")
            skip += 1
            continue

        print(f"[{i}/{total}] {ticker_str} {form_type} {date_str}  {url[:80]}")

        result = _fetch_one(client, filing_id, url, dry_run=dry_run)
        if result is None:
            if dry_run:
                skip += 1
            else:
                err += 1
            continue

        raw_html, clean_text, table_json = result

        try:
            _insert_document(con, filing_id, raw_html, clean_text, table_json)
            ok += 1
        except Exception as exc:
            print(f"  DB error: {exc}")
            traceback.print_exc()
            err += 1

    con.close()
    print(f"\nDone. ok={ok}  skip={skip}  err={err}")


# ── CLI ────────────────────────────────────────────────────────────────────────

def _parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Download and parse primary filing documents from EDGAR."
    )
    p.add_argument("--ticker", help="Process only this ticker (e.g. AAPL)")
    p.add_argument("--limit", type=int, help="Max filings to process")
    p.add_argument("--dry_run", action="store_true",
                   help="Print URLs but do not write to DB")
    return p.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    fetch_documents(
        ticker=args.ticker,
        limit=args.limit,
        dry_run=args.dry_run,
    )
