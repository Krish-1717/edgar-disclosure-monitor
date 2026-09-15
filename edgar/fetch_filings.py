"""
fetch_filings.py — Pull filing metadata from EDGAR into SQLite.

Day 1: For each company in the watchlist, fetch submission history and
store every 10-K and 10-Q since MIN_FILING_DATE into the filings table.

Done when: a table holds every 10-K and 10-Q for 25 companies since 2019.

Usage:
    python edgar/fetch_filings.py
    python edgar/fetch_filings.py --ticker AAPL MSFT  # specific tickers
    python edgar/fetch_filings.py --dry_run           # print without writing
"""

import argparse
import logging
import sqlite3
from datetime import date
from pathlib import Path
from typing import List, Optional

from edgar.client import EdgarClient
from edgar.watchlist import WATCHLIST, FORM_TYPES, MIN_FILING_DATE

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "edgar.db"

# ── DB helpers ────────────────────────────────────────────────────────────────

def init_db(db_path: Path) -> sqlite3.Connection:
    """Open (or create) the SQLite database and apply schema."""
    schema_path = Path(__file__).parent.parent / "db" / "schema.sql"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.commit()
    return conn


def upsert_company(conn: sqlite3.Connection, cik: str, ticker: str, name: str, sector: str):
    conn.execute(
        """
        INSERT OR REPLACE INTO companies (cik, ticker, name, sector)
        VALUES (?, ?, ?, ?)
        """,
        (cik, ticker, name, sector),
    )


def upsert_filing(conn: sqlite3.Connection, row: dict) -> bool:
    """
    Insert filing if not already present.
    Returns True if inserted, False if already existed.
    """
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO filings
                (cik, ticker, form_type, filing_date, period_of_report, accession, primary_doc_url)
            VALUES
                (:cik, :ticker, :form_type, :filing_date, :period_of_report, :accession, :primary_doc_url)
            """,
            row,
        )
        return conn.total_changes > 0
    except sqlite3.IntegrityError as e:
        logger.warning("DB integrity error for %s: %s", row.get("accession"), e)
        return False


# ── Primary doc URL resolution ────────────────────────────────────────────────

def _primary_doc_url(cik_numeric: str, accession: str, docs: List[str]) -> Optional[str]:
    """
    Pick the primary document URL from a filing's document list.
    Prefers .htm/.html over .txt.
    """
    acc_nodash = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik_numeric}/{acc_nodash}/"

    # Prefer the first .htm document that isn't an index or exhibit
    for doc in docs:
        low = doc.lower()
        if low.endswith((".htm", ".html")) and "index" not in low and "ex" not in low[:6]:
            return base + doc

    # Fall back to any .htm
    for doc in docs:
        if doc.lower().endswith((".htm", ".html")):
            return base + doc

    # Last resort: .txt
    for doc in docs:
        if doc.lower().endswith(".txt"):
            return base + doc

    return None


# ── Core fetch logic ──────────────────────────────────────────────────────────

def fetch_filings_for_ticker(
    client: EdgarClient,
    conn: sqlite3.Connection,
    ticker: str,
    name: str,
    sector: str,
    dry_run: bool = False,
) -> dict:
    """
    Fetch and store all 10-K and 10-Q filings since MIN_FILING_DATE for one ticker.

    Returns a summary dict with counts.
    """
    cik = client.ticker_to_cik(ticker)
    if not cik:
        logger.error("CIK not found for %s", ticker)
        return {"ticker": ticker, "error": "CIK not found", "inserted": 0, "skipped": 0}

    cik_numeric = str(int(cik))  # drop leading zeros for URL construction

    logger.info("Fetching submissions for %s (CIK %s) ...", ticker, cik)
    subs = client.get_submissions(cik)

    if not dry_run:
        upsert_company(conn, cik, ticker, subs.get("name", name), sector)

    recent = subs.get("filings", {}).get("recent", {})
    forms      = recent.get("form", [])
    dates      = recent.get("filingDate", [])
    periods    = recent.get("reportDate", [])
    accessions = recent.get("accessionNumber", [])
    doc_lists  = recent.get("primaryDocument", [])  # list of primary doc filenames

    inserted = 0
    skipped  = 0

    for form, filing_date, period, acc, doc_name in zip(
        forms, dates, periods, accessions, doc_lists
    ):
        if form not in FORM_TYPES:
            continue
        if filing_date < MIN_FILING_DATE:
            continue

        acc_clean = acc  # e.g. "0001234567-23-000001"

        # Build primary doc URL
        primary_url = _primary_doc_url(
            cik_numeric, acc_clean, [doc_name] if doc_name else []
        )

        row = {
            "cik":              cik,
            "ticker":           ticker,
            "form_type":        form,
            "filing_date":      filing_date,
            "period_of_report": period or None,
            "accession":        acc_clean,
            "primary_doc_url":  primary_url,
        }

        if dry_run:
            logger.info("  DRY RUN: %s %s %s %s", ticker, form, filing_date, acc_clean)
            inserted += 1
        else:
            if upsert_filing(conn, row):
                inserted += 1
                logger.debug("  Inserted: %s %s %s", ticker, form, filing_date)
            else:
                skipped += 1

    if not dry_run:
        conn.commit()

    logger.info(
        "  %s: inserted=%d, skipped=%d (form types seen: 10-K/10-Q only)",
        ticker, inserted, skipped,
    )
    return {"ticker": ticker, "cik": cik, "inserted": inserted, "skipped": skipped}


def run(tickers: Optional[List[str]] = None, dry_run: bool = False) -> None:
    """
    Pull filing metadata for all (or a subset of) watchlist companies.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    client = EdgarClient()
    conn   = None if dry_run else init_db(DB_PATH)

    target = [
        c for c in WATCHLIST
        if tickers is None or c["ticker"].upper() in {t.upper() for t in tickers}
    ]

    print(f"Fetching filing metadata for {len(target)} companies ...")
    if dry_run:
        print("  (DRY RUN — nothing written to DB)")

    total_inserted = 0
    total_skipped  = 0
    errors         = []

    for company in target:
        result = fetch_filings_for_ticker(
            client, conn,
            company["ticker"],
            company["name"],
            company["sector"],
            dry_run=dry_run,
        )
        if "error" in result:
            errors.append(result)
        else:
            total_inserted += result["inserted"]
            total_skipped  += result["skipped"]

    print("\n=== Summary ===")
    print(f"  Companies processed : {len(target)}")
    print(f"  Filings inserted    : {total_inserted}")
    print(f"  Filings skipped     : {total_skipped}")
    if errors:
        print(f"  Errors              : {len(errors)}")
        for e in errors:
            print(f"    - {e}")

    if conn:
        # Verify row counts
        n_companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        n_filings   = conn.execute("SELECT COUNT(*) FROM filings").fetchone()[0]
        print(f"\nDB now holds {n_companies} companies and {n_filings} filings.")
        print(f"  10-K: {conn.execute('SELECT COUNT(*) FROM filings WHERE form_type=\'10-K\'').fetchone()[0]}")
        print(f"  10-Q: {conn.execute('SELECT COUNT(*) FROM filings WHERE form_type=\'10-Q\'').fetchone()[0]}")
        conn.close()

    print("\nDay 1 Done: fetch_filings.py OK")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Fetch EDGAR filing metadata into SQLite")
    p.add_argument("--ticker",  nargs="+", help="Limit to specific tickers (default: all 25)")
    p.add_argument("--dry_run", action="store_true", help="Print without writing to DB")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(tickers=args.ticker, dry_run=args.dry_run)
