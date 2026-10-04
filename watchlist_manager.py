"""
watchlist_manager.py — Dynamic Watchlist Manager for EDGAR Disclosure Monitor

Manages the list of companies to track, supporting:
  - Add/remove individual tickers (with CIK auto-lookup)
  - Import S&P 500 or other index constituents
  - Sector and tag-based grouping
  - Export/import watchlist as JSON or CSV
  - View stats: alert counts, last filing date, coverage

Usage:
    python watchlist_manager.py list
    python watchlist_manager.py add NVDA --sector Technology
    python watchlist_manager.py remove TSLA
    python watchlist_manager.py import-sp500          # pulls live S&P 500 list
    python watchlist_manager.py export --output data/watchlist_export.json
    python watchlist_manager.py stats
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import pathlib
import sqlite3
import time
from typing import Optional

log = logging.getLogger(__name__)


# ── S&P 500 constituent list (Wikipedia scrape) ────────────────────────────────

def fetch_sp500_constituents() -> list[dict]:
    """
    Scrape the S&P 500 constituent list from Wikipedia.
    Returns list of dicts: {ticker, name, sector, sub_industry, headquarters}
    Falls back to a built-in core list if the request fails.
    """
    try:
        import requests
        from html.parser import HTMLParser

        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        resp = requests.get(url, timeout=30, headers={"User-Agent": "edgar-monitor/1.0"})
        resp.raise_for_status()

        # Simple table parse: find the constituents table
        companies: list[dict] = []
        import re
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", resp.text, re.DOTALL)
        for row in rows[1:]:  # skip header
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
            if len(cells) < 4:
                continue
            def clean(s: str) -> str:
                return re.sub(r"<[^>]+>", "", s).strip()
            ticker = clean(cells[0]).replace("\n", "").split(" ")[0]
            name   = clean(cells[1])
            sector = clean(cells[2])
            if ticker and len(ticker) <= 5:
                companies.append({
                    "ticker": ticker,
                    "name":   name,
                    "sector": sector,
                })
        if companies:
            log.info("Fetched %d S&P 500 constituents from Wikipedia", len(companies))
            return companies
    except Exception as e:
        log.warning("S&P 500 Wikipedia scrape failed: %s. Using fallback list.", e)

    # Fallback: most-common S&P 500 names across sectors
    return CORE_SP500_FALLBACK


CORE_SP500_FALLBACK: list[dict] = [
    # Technology
    {"ticker": "AAPL",  "name": "Apple Inc.",                     "sector": "Technology"},
    {"ticker": "MSFT",  "name": "Microsoft Corporation",          "sector": "Technology"},
    {"ticker": "NVDA",  "name": "NVIDIA Corporation",             "sector": "Technology"},
    {"ticker": "GOOGL", "name": "Alphabet Inc. (Class A)",        "sector": "Technology"},
    {"ticker": "META",  "name": "Meta Platforms Inc.",            "sector": "Technology"},
    {"ticker": "AVGO",  "name": "Broadcom Inc.",                  "sector": "Technology"},
    {"ticker": "ORCL",  "name": "Oracle Corporation",             "sector": "Technology"},
    {"ticker": "AMD",   "name": "Advanced Micro Devices",         "sector": "Technology"},
    {"ticker": "QCOM",  "name": "Qualcomm Incorporated",          "sector": "Technology"},
    {"ticker": "TXN",   "name": "Texas Instruments",              "sector": "Technology"},
    {"ticker": "CRM",   "name": "Salesforce Inc.",                "sector": "Technology"},
    {"ticker": "ADBE",  "name": "Adobe Inc.",                     "sector": "Technology"},
    {"ticker": "INTC",  "name": "Intel Corporation",              "sector": "Technology"},
    # Financials
    {"ticker": "JPM",   "name": "JPMorgan Chase & Co.",           "sector": "Financials"},
    {"ticker": "BAC",   "name": "Bank of America Corp.",          "sector": "Financials"},
    {"ticker": "WFC",   "name": "Wells Fargo & Company",          "sector": "Financials"},
    {"ticker": "GS",    "name": "Goldman Sachs Group Inc.",       "sector": "Financials"},
    {"ticker": "MS",    "name": "Morgan Stanley",                 "sector": "Financials"},
    {"ticker": "BRK-B", "name": "Berkshire Hathaway Inc.",        "sector": "Financials"},
    {"ticker": "V",     "name": "Visa Inc.",                      "sector": "Financials"},
    {"ticker": "MA",    "name": "Mastercard Incorporated",        "sector": "Financials"},
    {"ticker": "AXP",   "name": "American Express Company",       "sector": "Financials"},
    {"ticker": "BLK",   "name": "BlackRock Inc.",                 "sector": "Financials"},
    # Healthcare
    {"ticker": "UNH",   "name": "UnitedHealth Group",             "sector": "Healthcare"},
    {"ticker": "JNJ",   "name": "Johnson & Johnson",              "sector": "Healthcare"},
    {"ticker": "LLY",   "name": "Eli Lilly and Company",          "sector": "Healthcare"},
    {"ticker": "ABT",   "name": "Abbott Laboratories",            "sector": "Healthcare"},
    {"ticker": "PFE",   "name": "Pfizer Inc.",                    "sector": "Healthcare"},
    {"ticker": "MRK",   "name": "Merck & Co. Inc.",               "sector": "Healthcare"},
    {"ticker": "AMGN",  "name": "Amgen Inc.",                     "sector": "Healthcare"},
    {"ticker": "TMO",   "name": "Thermo Fisher Scientific",       "sector": "Healthcare"},
    # Consumer Discretionary
    {"ticker": "AMZN",  "name": "Amazon.com Inc.",                "sector": "Consumer Discretionary"},
    {"ticker": "TSLA",  "name": "Tesla Inc.",                     "sector": "Consumer Discretionary"},
    {"ticker": "HD",    "name": "Home Depot Inc.",                "sector": "Consumer Discretionary"},
    {"ticker": "MCD",   "name": "McDonald's Corporation",         "sector": "Consumer Discretionary"},
    {"ticker": "NKE",   "name": "Nike Inc.",                      "sector": "Consumer Discretionary"},
    {"ticker": "SBUX",  "name": "Starbucks Corporation",          "sector": "Consumer Discretionary"},
    {"ticker": "LOW",   "name": "Lowe's Companies Inc.",          "sector": "Consumer Discretionary"},
    # Communication Services
    {"ticker": "NFLX",  "name": "Netflix Inc.",                   "sector": "Communication Services"},
    {"ticker": "DIS",   "name": "The Walt Disney Company",        "sector": "Communication Services"},
    {"ticker": "CMCSA", "name": "Comcast Corporation",            "sector": "Communication Services"},
    {"ticker": "VZ",    "name": "Verizon Communications",         "sector": "Communication Services"},
    {"ticker": "T",     "name": "AT&T Inc.",                      "sector": "Communication Services"},
    # Energy
    {"ticker": "XOM",   "name": "Exxon Mobil Corporation",        "sector": "Energy"},
    {"ticker": "CVX",   "name": "Chevron Corporation",            "sector": "Energy"},
    {"ticker": "COP",   "name": "ConocoPhillips",                 "sector": "Energy"},
    {"ticker": "SLB",   "name": "SLB (Schlumberger)",             "sector": "Energy"},
    {"ticker": "EOG",   "name": "EOG Resources Inc.",             "sector": "Energy"},
    # Industrials
    {"ticker": "CAT",   "name": "Caterpillar Inc.",               "sector": "Industrials"},
    {"ticker": "BA",    "name": "Boeing Company",                 "sector": "Industrials"},
    {"ticker": "GE",    "name": "GE Aerospace",                   "sector": "Industrials"},
    {"ticker": "HON",   "name": "Honeywell International",        "sector": "Industrials"},
    {"ticker": "RTX",   "name": "RTX Corporation",                "sector": "Industrials"},
    {"ticker": "UPS",   "name": "United Parcel Service",          "sector": "Industrials"},
    # Consumer Staples
    {"ticker": "PG",    "name": "Procter & Gamble Company",       "sector": "Consumer Staples"},
    {"ticker": "KO",    "name": "Coca-Cola Company",              "sector": "Consumer Staples"},
    {"ticker": "PEP",   "name": "PepsiCo Inc.",                   "sector": "Consumer Staples"},
    {"ticker": "WMT",   "name": "Walmart Inc.",                   "sector": "Consumer Staples"},
    {"ticker": "COST",  "name": "Costco Wholesale Corporation",   "sector": "Consumer Staples"},
    {"ticker": "MDLZ",  "name": "Mondelez International",         "sector": "Consumer Staples"},
    # Utilities
    {"ticker": "NEE",   "name": "NextEra Energy Inc.",            "sector": "Utilities"},
    {"ticker": "DUK",   "name": "Duke Energy Corporation",        "sector": "Utilities"},
    {"ticker": "SO",    "name": "Southern Company",               "sector": "Utilities"},
    # Real Estate
    {"ticker": "AMT",   "name": "American Tower Corporation",     "sector": "Real Estate"},
    {"ticker": "PLD",   "name": "Prologis Inc.",                  "sector": "Real Estate"},
    {"ticker": "EQIX",  "name": "Equinix Inc.",                   "sector": "Real Estate"},
    # Materials
    {"ticker": "LIN",   "name": "Linde plc",                      "sector": "Materials"},
    {"ticker": "APD",   "name": "Air Products & Chemicals",       "sector": "Materials"},
    {"ticker": "ECL",   "name": "Ecolab Inc.",                    "sector": "Materials"},
]


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    from database import get_connection, init_db
    conn = get_connection()
    init_db(conn)
    return conn


def _lookup_cik(ticker: str) -> str:
    """Attempt to resolve CIK from SEC EDGAR ticker-to-CIK map."""
    try:
        from edgar_client import EdgarClient
        ua = os.getenv("EDGAR_USER_AGENT", "Krish Patel patelkrish1717@gmail.com")
        client = EdgarClient(ua)
        return client.ticker_to_cik(ticker.upper()) or ""
    except Exception as e:
        log.debug("CIK lookup failed for %s: %s", ticker, e)
        return ""


# ── Core operations ────────────────────────────────────────────────────────────

def add_company(
    conn: sqlite3.Connection,
    ticker: str,
    name: Optional[str] = None,
    sector: Optional[str] = "Unknown",
    cik: Optional[str] = None,
) -> dict:
    """
    Add a company to the watchlist DB.
    Resolves CIK from EDGAR if not provided.
    Returns the resulting row dict.
    """
    from database import upsert_company, transaction

    ticker = ticker.upper()
    if cik is None:
        cik = _lookup_cik(ticker)
    if not name:
        name = ticker

    with transaction(conn):
        upsert_company(conn, ticker, name, sector or "Unknown", cik or "")

    log.info("Added %s (%s) to watchlist — CIK: %s", ticker, sector, cik or "unknown")
    return {"ticker": ticker, "name": name, "sector": sector, "cik": cik}


def remove_company(conn: sqlite3.Connection, ticker: str) -> bool:
    """Remove a company from the watchlist. Returns True if removed, False if not found."""
    ticker = ticker.upper()
    cur = conn.execute("DELETE FROM companies WHERE ticker = ?", (ticker,))
    conn.commit()
    removed = cur.rowcount > 0
    if removed:
        log.info("Removed %s from watchlist", ticker)
    else:
        log.warning("Ticker %s not found in watchlist", ticker)
    return removed


def list_companies(
    conn: sqlite3.Connection,
    sector: Optional[str] = None,
    sort_by: str = "ticker",
) -> list[dict]:
    """
    Return all companies in the watchlist, with alert counts.
    """
    query = """
        SELECT c.ticker, c.name, c.sector, c.cik,
               COUNT(DISTINCT f.id)          AS n_filings,
               COUNT(DISTINCT a.id)          AS n_alerts,
               MAX(a.filed)                  AS last_alert_date,
               MAX(a.ranking)                AS max_rank
        FROM companies c
        LEFT JOIN filings f ON f.ticker = c.ticker AND f.fetched = 1
        LEFT JOIN alerts  a ON a.ticker = c.ticker
    """
    params = []
    if sector:
        query += " WHERE c.sector = ?"
        params.append(sector)
    query += " GROUP BY c.ticker"

    valid_sorts = {"ticker", "sector", "n_alerts", "n_filings", "max_rank"}
    if sort_by not in valid_sorts:
        sort_by = "ticker"
    query += f" ORDER BY {sort_by}"

    return [dict(r) for r in conn.execute(query, params).fetchall()]


def import_companies(
    conn: sqlite3.Connection,
    companies: list[dict],
    skip_existing: bool = True,
    resolve_cik: bool = True,
    rate_limit_sec: float = 0.15,
) -> dict:
    """
    Bulk-import a list of companies.
    companies: list of {ticker, name, sector} dicts.
    Returns {added, skipped, errors}.
    """
    from database import upsert_company, transaction

    existing = {r[0] for r in conn.execute("SELECT ticker FROM companies")}
    added = skipped = errors = 0

    for co in companies:
        ticker = co.get("ticker", "").upper().strip()
        if not ticker or len(ticker) > 6:
            continue

        if skip_existing and ticker in existing:
            skipped += 1
            continue

        try:
            cik = ""
            if resolve_cik:
                cik = _lookup_cik(ticker)
                time.sleep(rate_limit_sec)

            with transaction(conn):
                upsert_company(
                    conn,
                    ticker,
                    co.get("name", ticker),
                    co.get("sector", "Unknown"),
                    cik,
                )
            existing.add(ticker)
            added += 1
            log.debug("Imported %s", ticker)
        except Exception as e:
            log.warning("Failed to import %s: %s", ticker, e)
            errors += 1

    return {"added": added, "skipped": skipped, "errors": errors}


def import_sp500(
    conn: sqlite3.Connection,
    skip_existing: bool = True,
    resolve_cik: bool = True,
) -> dict:
    """
    Import the S&P 500 constituent list into the watchlist.
    """
    log.info("Fetching S&P 500 constituent list...")
    companies = fetch_sp500_constituents()
    log.info("Importing %d companies...", len(companies))
    return import_companies(conn, companies, skip_existing=skip_existing, resolve_cik=resolve_cik)


# ── Export / import ────────────────────────────────────────────────────────────

def export_watchlist_json(conn: sqlite3.Connection, path: pathlib.Path) -> pathlib.Path:
    """Export watchlist to JSON."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list_companies(conn)
    path.write_text(json.dumps(rows, indent=2))
    log.info("Exported %d companies to %s", len(rows), path)
    return path


def export_watchlist_csv(conn: sqlite3.Connection, path: pathlib.Path) -> pathlib.Path:
    """Export watchlist to CSV."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list_companies(conn)
    if rows:
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    log.info("Exported %d companies to %s", len(rows), path)
    return path


def import_from_json(conn: sqlite3.Connection, path: pathlib.Path) -> dict:
    """Import companies from a JSON watchlist export."""
    companies = json.loads(pathlib.Path(path).read_text())
    return import_companies(conn, companies, resolve_cik=False)


def import_from_csv(conn: sqlite3.Connection, path: pathlib.Path) -> dict:
    """Import companies from a CSV file with columns: ticker, name, sector."""
    with open(path, newline="") as f:
        companies = list(csv.DictReader(f))
    return import_companies(conn, companies, resolve_cik=False)


# ── Stats ──────────────────────────────────────────────────────────────────────

def watchlist_stats(conn: sqlite3.Connection) -> dict:
    """Return summary statistics for the watchlist."""
    rows = list_companies(conn)
    sectors: dict[str, int] = {}
    for r in rows:
        sectors[r["sector"] or "Unknown"] = sectors.get(r["sector"] or "Unknown", 0) + 1

    total_alerts = sum(r["n_alerts"] for r in rows)
    covered = sum(1 for r in rows if r["n_filings"] > 0)
    critical = sum(1 for r in rows if (r["max_rank"] or 0) >= 5)
    high     = sum(1 for r in rows if (r["max_rank"] or 0) >= 4)

    return {
        "total_companies": len(rows),
        "covered_companies": covered,
        "total_alerts": total_alerts,
        "companies_with_critical_alert": critical,
        "companies_with_high_alert": high,
        "by_sector": dict(sorted(sectors.items(), key=lambda x: x[1], reverse=True)),
    }


def print_stats(stats: dict) -> None:
    print(f"\n{'═'*50}")
    print("  WATCHLIST STATISTICS")
    print(f"{'═'*50}")
    print(f"  Companies tracked:    {stats['total_companies']}")
    print(f"  With filing data:     {stats['covered_companies']}")
    print(f"  Total alerts:         {stats['total_alerts']}")
    print(f"  CRITICAL/HIGH alerts: {stats['companies_with_high_alert']} companies")
    print(f"\n  By sector:")
    for sector, n in stats["by_sector"].items():
        print(f"    {sector:<30} {n}")
    print(f"{'═'*50}\n")


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="EDGAR Watchlist Manager")
    sub = parser.add_subparsers(dest="cmd")

    # list
    p_list = sub.add_parser("list", help="List all watched companies")
    p_list.add_argument("--sector", help="Filter by sector")
    p_list.add_argument("--sort-by", default="ticker",
                        choices=["ticker", "sector", "n_alerts", "n_filings", "max_rank"])

    # add
    p_add = sub.add_parser("add", help="Add a company")
    p_add.add_argument("ticker")
    p_add.add_argument("--name",   default="")
    p_add.add_argument("--sector", default="Unknown")
    p_add.add_argument("--cik",    default=None)

    # remove
    p_rm = sub.add_parser("remove", help="Remove a company")
    p_rm.add_argument("ticker")

    # import-sp500
    p_sp = sub.add_parser("import-sp500", help="Import S&P 500 constituents")
    p_sp.add_argument("--no-cik",         action="store_true", help="Skip CIK resolution")
    p_sp.add_argument("--include-existing", action="store_true", help="Re-upsert existing")

    # export
    p_exp = sub.add_parser("export", help="Export watchlist")
    p_exp.add_argument("--output", default="data/watchlist_export.json")
    p_exp.add_argument("--csv",    action="store_true", help="Export as CSV instead of JSON")

    # import
    p_imp = sub.add_parser("import", help="Import watchlist from file")
    p_imp.add_argument("path", help="JSON or CSV file path")

    # stats
    sub.add_parser("stats", help="Show watchlist statistics")

    args = parser.parse_args()

    conn = _get_conn()

    if args.cmd == "list":
        rows = list_companies(conn, sector=args.sector, sort_by=args.sort_by)
        if not rows:
            print("No companies in watchlist.")
        else:
            header = f"{'TICKER':<8} {'SECTOR':<25} {'COMPANY':<35} {'FILES':>6} {'ALERTS':>7} {'MAX RANK':>9}"
            print(header)
            print("─" * len(header))
            for r in rows:
                print(
                    f"{r['ticker']:<8} {(r['sector'] or '—'):<25} {r['name'][:33]:<35} "
                    f"{r['n_filings']:>6} {r['n_alerts']:>7} {r['max_rank'] or '—':>9}"
                )

    elif args.cmd == "add":
        result = add_company(conn, args.ticker, name=args.name,
                             sector=args.sector, cik=args.cik)
        print(f"✓ Added: {result}")

    elif args.cmd == "remove":
        removed = remove_company(conn, args.ticker)
        if removed:
            print(f"✓ Removed {args.ticker.upper()} from watchlist")
        else:
            print(f"✗ {args.ticker.upper()} not found in watchlist")

    elif args.cmd == "import-sp500":
        result = import_sp500(
            conn,
            skip_existing=not args.include_existing,
            resolve_cik=not args.no_cik,
        )
        print(f"✓ Import complete: {result}")

    elif args.cmd == "export":
        path = pathlib.Path(args.output)
        if args.csv:
            path = path.with_suffix(".csv")
            export_watchlist_csv(conn, path)
        else:
            export_watchlist_json(conn, path)
        print(f"✓ Exported to {path}")

    elif args.cmd == "import":
        p = pathlib.Path(args.path)
        if p.suffix == ".csv":
            result = import_from_csv(conn, p)
        else:
            result = import_from_json(conn, p)
        print(f"✓ Import complete: {result}")

    elif args.cmd == "stats":
        stats = watchlist_stats(conn)
        print_stats(stats)

    else:
        parser.print_help()

    conn.close()
