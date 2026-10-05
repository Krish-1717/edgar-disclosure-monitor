"""
run_pipeline.py — End-to-End Ingestion Pipeline (v2)

Usage:
    python run_pipeline.py --tickers AAPL MSFT GOOGL
    python run_pipeline.py --all          # full watchlist
    python run_pipeline.py --ticker AAPL  # single company
    python run_pipeline.py --ticker AAPL --no-news    # skip news enrichment
    python run_pipeline.py --ticker AAPL --no-llm     # skip LLM classification
    python run_pipeline.py --ticker AAPL --no-finance # skip financial metrics

Steps per filing:
  1.  Fetch + cache raw HTML
  2.  Strip to clean text
  3.  Segment into Items
  4.  Store sections in DB
  5.  Find comparable prior filing
  6.  Align paragraphs + compute diffs
  7.  Score changes → build alert
  8.  Insert alert into DB
  9.  Enrich with real news coverage score (news_fetcher)
  10. Enrich with financial return metrics (financial_metrics)
  11. LLM classify changed paragraphs (llm_classifier, optional)
"""
from __future__ import annotations
import argparse
import logging
import os
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

USER_AGENT = os.getenv("EDGAR_USER_AGENT", "Krish Patel patelkrish1717@gmail.com")
TEXT_DIR   = pathlib.Path("data/filings")


def run(
    tickers: list[str],
    enrich_news: bool    = True,
    enrich_finance: bool = True,
    enrich_llm: bool     = False,   # off by default (needs OPENAI_API_KEY)
) -> None:
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

    # ── Per-ticker ingestion ───────────────────────────────────────────────────
    for ticker in tickers:
        log.info("── Processing %s ──", ticker)
        try:
            _process_ticker(client, conn, ticker)
        except Exception as e:
            log.error("Failed %s: %s", ticker, e, exc_info=True)

    # ── Post-ingestion enrichment ──────────────────────────────────────────────

    if enrich_news:
        _enrich_news(conn, tickers)

    if enrich_finance:
        _enrich_finance(conn)

    if enrich_llm:
        _enrich_llm(conn, tickers)

    conn.close()
    log.info("Pipeline complete.")


# ── Ingestion ──────────────────────────────────────────────────────────────────

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

        # Build + store alert (normalized_coverage starts at 0.5; enriched below)
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


# ── Enrichment helpers ─────────────────────────────────────────────────────────

def _enrich_news(conn, tickers: list[str]) -> None:
    """
    Fetch real press coverage scores for each alert and update attention_gap.
    Uses news_fetcher.get_coverage_score().
    """
    log.info("── News enrichment ──")
    try:
        from news_fetcher import get_coverage_score
    except ImportError:
        log.warning("news_fetcher not available — skipping news enrichment")
        return

    # Get alerts for our tickers that need coverage enrichment
    placeholders = ",".join("?" * len(tickers))
    alerts = conn.execute(
        f"""SELECT a.id, a.ticker, a.filed, a.materiality_score, a.burial_score,
                   c.name
            FROM alerts a
            JOIN companies c ON c.ticker = a.ticker
            WHERE a.ticker IN ({placeholders})
            ORDER BY a.filed DESC
        """,
        tickers,
    ).fetchall()

    # Ensure columns exist (migration-safe)
    for col, coltype in [("normalized_coverage", "REAL"), ("article_count", "INTEGER")]:
        try:
            conn.execute(f"ALTER TABLE alerts ADD COLUMN {col} {coltype}")
            conn.commit()
        except Exception:
            pass  # column already exists

    updated = 0
    for alert in alerts:
        try:
            # FIX: news_fetcher v2 returns 4-tuple (composite_score, article_count, sentiment_direction, top_bucket)
            composite, article_count, direction, bucket = get_coverage_score(
                alert["ticker"],
                alert["name"],
                alert["filed"],
            )
            # Recompute attention gap with real coverage
            from financial_metrics import combined_attention_gap
            from change_scorer import rank_alert
            new_gap  = combined_attention_gap(alert["materiality_score"], composite)
            new_rank = rank_alert(alert["materiality_score"], alert["burial_score"], new_gap)
            with transaction(conn):
                conn.execute("""
                    UPDATE alerts
                    SET attention_gap = ?, ranking = ?, normalized_coverage = ?,
                        article_count = ?
                    WHERE id = ?
                """, (new_gap, new_rank, composite, article_count, alert["id"]))
            updated += 1
            log.debug(
                "  %s %s: coverage=%.2f articles=%d gap=%.1f rank=%d",
                alert["ticker"], alert["filed"],
                composite, article_count, direction, new_gap, new_rank,
            )
        except Exception as e:
            log.warning("News enrichment failed for alert %d: %s", alert["id"], e)
        time.sleep(0.3)  # gentle rate limit for news fetching

    log.info("  News enrichment: %d alerts updated", updated)


def _enrich_finance(conn) -> None:
    """
    Enrich alerts with event-study return metrics (yfinance).
    Uses financial_metrics.enrich_alerts_with_returns().
    """
    log.info("── Financial metrics enrichment ──")
    try:
        from financial_metrics import enrich_alerts_with_returns
        n = enrich_alerts_with_returns(conn, limit=50)
        log.info("  Financial enrichment: %d alerts updated", n)
    except ImportError:
        log.warning("financial_metrics not available — install yfinance")
    except Exception as e:
        log.warning("Financial enrichment error: %s", e)


def _enrich_llm(conn, tickers: list[str]) -> None:
    """
    Classify changed paragraphs with GPT-4o-mini.
    Uses llm_classifier.classify_changes().
    Requires OPENAI_API_KEY env var.
    """
    log.info("── LLM classification ──")
    if not os.getenv("OPENAI_API_KEY"):
        log.warning("OPENAI_API_KEY not set — skipping LLM classification")
        return
    try:
        from llm_classifier import classify_changes
    except ImportError:
        log.warning("llm_classifier not available — install openai")
        return

    placeholders = ",".join("?" * len(tickers))
    alerts = conn.execute(
        f"""SELECT a.id, a.ticker, a.new_filing_id
            FROM alerts a
            WHERE a.ticker IN ({placeholders})
            ORDER BY a.filed DESC
            LIMIT 20
        """,
        tickers,
    ).fetchall()

    for alert in alerts:
        try:
            n = classify_changes(conn, alert["new_filing_id"], alert["ticker"], limit=15)
            log.info("  LLM classified %d paragraphs for %s alert %d",
                     n, alert["ticker"], alert["id"])
        except Exception as e:
            log.warning("LLM classification failed for alert %d: %s", alert["id"], e)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="EDGAR Disclosure Monitor pipeline v2")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all",     action="store_true",   help="Run full watchlist")
    group.add_argument("--ticker",  type=str,              help="Single ticker")
    group.add_argument("--tickers", nargs="+",             help="Multiple tickers")
    parser.add_argument("--no-news",    action="store_true", help="Skip news enrichment")
    parser.add_argument("--no-finance", action="store_true", help="Skip financial metrics")
    parser.add_argument("--no-llm",     action="store_true", help="Skip LLM classification")
    parser.add_argument("--with-llm",   action="store_true", help="Enable LLM classification")
    args = parser.parse_args()

    if args.all:
        tickers = [w["ticker"] for w in WATCHLIST]
    elif args.ticker:
        tickers = [args.ticker.upper()]
    else:
        tickers = [t.upper() for t in args.tickers]

    run(
        tickers,
        enrich_news    = not args.no_news,
        enrich_finance = not args.no_finance,
        enrich_llm     = args.with_llm and not args.no_llm,
    )


if __name__ == "__main__":
    main()
