"""
run_pipeline.py — End-to-End Ingestion Pipeline

Usage:
    python run_pipeline.py --tickers AAPL MSFT GOOGL
    python run_pipeline.py --all          # full watchlist
    python run_pipeline.py --ticker AAPL  # single company

Steps per filing:
  1. Fetch + cache raw HTML
  2. Strip to clean text
  3. Segment into Items
  4. Store sections in DB
  5. Find comparable prior filing
  6. Align paragraphs + compute diffs
  7. Score changes → build alert
  8. Insert alert into DB
"""
from __future__ import annotations
import argparse
import logging
import pathlib
import sys
import time

from edgar_client import EdgarClient
from database import (
    get_connection, init_db, transaction,
    upsert_company, insert_filing,
    get_prior_comparable_filing, get_sections,
)
from section_segmenter import (
    html_to_clean_text, segment_sections, save_clean_text,
)
from paragraph_aligner import diff_sections
from change_scorer import build_alert
from watchlist import WATCHLIST

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("pipeline")

USER_AGENT = "Krish Patel patelkrish1717@gmail.com"
TEXT_DIR   = pathlib.Path("data/filings")


def run(tickers: list[str]) -> None:
    client = EdgarClient(USER_AGENT)
    conn   = get_connection()
    init_db(conn)

    # Resolve CIKs and seed watchlist
    log.info("Seeding company watchlist...")
    try:
        cik_map = client.get_ticker_cik_map()
    except Exception as e:
        log.error("Could not fetch ticker-CIK map: %s", e)
        sys.exit(1)

    watchlist_lookup = {w["ticker"]: w for w in WATCHLIST}
    for ticker in tickers:
        info = watchlist_lookup.get(ticker, {"name": ticker, "sector": "Unknown"})
        cik  = cik_map.get(ticker.upper(), "")
        with transaction(conn):
            upsert_company(conn, ticker, info["name"], info["sector"], cik)

    for ticker in tickers:
        log.info("── Processing %s ──", ticker)
        try:
            _process_ticker(client, conn, ticker)
        except Exception as e:
            log.error("Failed %s: %s", ticker, e, exc_info=True)

    conn.close()
    log.info("Pipeline complete.")


def _process_ticker(client: EdgarClient, conn, ticker: str) -> None:
    filings = client.get_filings_metadata(ticker, since_year=2019)
    log.info("  %s: %d filings found", ticker, len(filings))

    for f in filings:
        # Insert metadata
        with transaction(conn):
            filing_id = insert_filing(conn, f)

        # Fetch and parse
        row = conn.execute("SELECT * FROM filings WHERE id=?", (filing_id,)).fetchone()
        if row["fetched"]:
            log.debug("  Skip (already fetched): %s %s", ticker, f["filed"])
            continue

        log.info("  Fetching %s %s %s", ticker, f["form"], f["filed"])
        try:
            html  = client.fetch_document_html(f["doc_url"])
            text  = html_to_clean_text(html)
        except Exception as e:
            log.warning("  Could not fetch %s: %s", f["doc_url"], e)
            continue

        # Save clean text
        text_path = TEXT_DIR / ticker / f"{f['accession'].replace('-', '')}.txt"
        save_clean_text(text, text_path)

        # Segment sections
        sections = segment_sections(text, f["form"])
        with transaction(conn):
            for item, body in sections.items():
                conn.execute("""
                    INSERT INTO sections (filing_id, item, text, word_count)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(filing_id, item) DO UPDATE SET text=excluded.text
                """, (filing_id, item, body, len(body.split())))
            conn.execute(
                "UPDATE filings SET fetched=1, clean_text_path=? WHERE id=?",
                (str(text_path), filing_id)
            )

        # Diff against prior comparable filing
        prior = get_prior_comparable_filing(conn, ticker, f["form"], f["filed"])
        if prior is None:
            log.debug("  No prior comparable for %s %s", ticker, f["filed"])
            continue

        prior_sections_rows = get_sections(conn, prior["id"])
        prior_sections = {r["item"]: r["text"] for r in prior_sections_rows}

        section_diffs = diff_sections(sections, prior_sections)

        # Store diffs
        with transaction(conn):
            for item, pairs in section_diffs.items():
                for p in pairs:
                    d = p.to_dict()
                    conn.execute("""
                        INSERT INTO changes
                          (new_filing_id, old_filing_id, item, change_type,
                           new_text, old_text, similarity, word_delta,
                           added_words, removed_words)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, (
                        filing_id, prior["id"], item, d["change_type"],
                        d["new_text"], d["old_text"], d["similarity"],
                        d["word_delta"], d["added_words"], d["removed_words"],
                    ))

        # Build + store alert
        alert = build_alert(
            ticker=ticker,
            new_filing_id=filing_id,
            old_filing_id=prior["id"],
            filed=f["filed"],
            period=f["period"],
            section_diffs=section_diffs,
        )
        with transaction(conn):
            conn.execute("""
                INSERT INTO alerts
                  (ticker, new_filing_id, old_filing_id, filed, period,
                   materiality_score, burial_score, attention_gap,
                   ranking, summary_items)
                VALUES
                  (:ticker, :new_filing_id, :old_filing_id, :filed, :period,
                   :materiality_score, :burial_score, :attention_gap,
                   :ranking, :summary_items)
            """, alert)

        log.info(
            "  Alert: materiality=%.1f burial=%.1f gap=%.1f rank=%d",
            alert["materiality_score"], alert["burial_score"],
            alert["attention_gap"], alert["ranking"],
        )
        time.sleep(0.1)  # courtesy pause between filings


def main() -> None:
    parser = argparse.ArgumentParser(description="EDGAR Disclosure Monitor pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all",    action="store_true",   help="Run full watchlist")
    group.add_argument("--ticker", type=str,              help="Single ticker")
    group.add_argument("--tickers", nargs="+",            help="Multiple tickers")
    args = parser.parse_args()

    if args.all:
        tickers = [w["ticker"] for w in WATCHLIST]
    elif args.ticker:
        tickers = [args.ticker.upper()]
    else:
        tickers = [t.upper() for t in args.tickers]

    run(tickers)


if __name__ == "__main__":
    main()
