"""
scheduler.py — Automated Pipeline Scheduler for EDGAR Disclosure Monitor

Runs the ingestion pipeline on a configurable schedule using APScheduler.
Designed to run as a long-lived background process (daemon or Docker container).

Default schedule:
  - Full watchlist:  Every day at 06:00 UTC (SEC typically posts filings overnight)
  - Single ticker:   On-demand via --ticker flag
  - Email digest:    Every day at 07:00 UTC (after pipeline completes)

Usage:
    python scheduler.py                        # start background scheduler
    python scheduler.py --once                 # run once immediately and exit
    python scheduler.py --ticker AAPL --once   # run single ticker once
    python scheduler.py --cron "0 8 * * 1-5"  # custom cron schedule

Environment:
    EMAIL_TO        : digest recipients (comma-separated)
    EDGAR_USER_AGENT: required by SEC (set in .env)
"""
from __future__ import annotations
import argparse
import logging
import os
import pathlib
import signal
import sys
import time
from datetime import datetime

log = logging.getLogger(__name__)

PIPELINE_HOUR   = int(os.getenv("PIPELINE_HOUR", "6"))    # 06:00 UTC
PIPELINE_MINUTE = int(os.getenv("PIPELINE_MINUTE", "0"))
DIGEST_HOUR     = int(os.getenv("DIGEST_HOUR", "7"))
DIGEST_MINUTE   = int(os.getenv("DIGEST_MINUTE", "0"))


# ── Pipeline runner ────────────────────────────────────────────────────────────

def run_pipeline_job(tickers: list[str] | None = None) -> None:
    """Execute the ingestion pipeline for all or specific tickers."""
    log.info("═══ Pipeline job started at %s ═══", datetime.utcnow().isoformat())
    try:
        from run_pipeline import run
        from watchlist import WATCHLIST

        targets = tickers or [w["ticker"] for w in WATCHLIST]
        log.info("Running pipeline for %d tickers: %s", len(targets), targets[:5])
        run(targets)
        log.info("═══ Pipeline job complete ═══")
    except Exception as e:
        log.error("Pipeline job failed: %s", e, exc_info=True)


def run_news_enrichment_job() -> None:
    """Fetch press coverage scores for recent alerts."""
    log.info("─── News enrichment job started ───")
    try:
        from database import get_connection, init_db
        from news_fetcher import get_coverage_score

        conn = get_connection()
        init_db(conn)

        # Find alerts without real coverage scores (currently all use default 0.5)
        alerts = conn.execute("""
            SELECT a.id, a.ticker, a.filed, c.name
            FROM alerts a
            LEFT JOIN companies c ON c.ticker = a.ticker
            ORDER BY a.id DESC LIMIT 20
        """).fetchall()

        for alert in alerts:
            try:
                score, count = get_coverage_score(
                    alert["ticker"],
                    alert["name"] or alert["ticker"],
                    alert["filed"],
                )
                # Recompute attention gap with real coverage
                mat = conn.execute(
                    "SELECT materiality_score FROM alerts WHERE id=?", (alert["id"],)
                ).fetchone()
                if mat:
                    new_gap = mat["materiality_score"] / max(score, 0.01)
                    conn.execute(
                        "UPDATE alerts SET attention_gap=? WHERE id=?",
                        (round(new_gap, 2), alert["id"])
                    )
                    conn.commit()
                    log.debug("Updated alert %d: coverage=%.3f gap=%.1f", alert["id"], score, new_gap)
            except Exception as e:
                log.warning("Coverage update failed for alert %d: %s", alert["id"], e)
                time.sleep(1)

        conn.close()
        log.info("─── News enrichment complete ───")
    except Exception as e:
        log.error("News enrichment job failed: %s", e, exc_info=True)


def run_financial_enrichment_job() -> None:
    """Fetch stock return data for recent alerts."""
    log.info("─── Financial enrichment job started ───")
    try:
        from database import get_connection, init_db
        from financial_metrics import enrich_alerts_with_returns

        conn = get_connection()
        init_db(conn)
        n = enrich_alerts_with_returns(conn, limit=30)
        conn.close()
        log.info("─── Financial enrichment complete: %d alerts enriched ───", n)
    except Exception as e:
        log.error("Financial enrichment failed: %s", e, exc_info=True)


def run_llm_classification_job() -> None:
    """Run LLM classification on unclassified changes."""
    if not os.getenv("OPENAI_API_KEY"):
        log.info("OPENAI_API_KEY not set — skipping LLM classification")
        return

    log.info("─── LLM classification job started ───")
    try:
        from database import get_connection, init_db
        from llm_classifier import classify_changes

        conn = get_connection()
        init_db(conn)

        # Find filings with unclassified changes
        filings = conn.execute("""
            SELECT DISTINCT f.id, f.ticker
            FROM filings f
            JOIN changes c ON c.new_filing_id = f.id
            WHERE c.llm_topic IS NULL AND c.change_type != 'unchanged'
            ORDER BY f.id DESC
            LIMIT 10
        """).fetchall()

        total = 0
        for f in filings:
            n = classify_changes(conn, f["id"], ticker=f["ticker"], limit=20)
            total += n

        conn.close()
        log.info("─── LLM classification complete: %d changes classified ───", total)
    except Exception as e:
        log.error("LLM classification job failed: %s", e, exc_info=True)


def run_digest_job() -> None:
    """Send the daily email digest."""
    log.info("─── Email digest job started ───")
    try:
        from database import get_connection, init_db
        from alert_emailer import send_digest

        conn = get_connection()
        init_db(conn)
        success = send_digest(conn, min_rank=4, days_back=1)
        conn.close()
        log.info("─── Email digest %s ───", "sent" if success else "failed")
    except Exception as e:
        log.error("Digest job failed: %s", e, exc_info=True)


# ── Scheduler setup ────────────────────────────────────────────────────────────

def start_scheduler(tickers: list[str] | None = None, cron_override: str | None = None) -> None:
    """Start the APScheduler background loop."""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        log.error("APScheduler not installed. Run: pip install apscheduler>=3.10.0")
        sys.exit(1)

    scheduler = BlockingScheduler(timezone="UTC")

    # Full pipeline
    if cron_override:
        trigger = CronTrigger.from_crontab(cron_override, timezone="UTC")
    else:
        trigger = CronTrigger(hour=PIPELINE_HOUR, minute=PIPELINE_MINUTE, timezone="UTC")

    scheduler.add_job(
        lambda: run_pipeline_job(tickers),
        trigger=trigger,
        id="pipeline",
        name="EDGAR Pipeline",
        misfire_grace_time=300,
        coalesce=True,
    )

    # Enrichment jobs (30 min after pipeline)
    scheduler.add_job(
        run_news_enrichment_job,
        CronTrigger(hour=PIPELINE_HOUR, minute=(PIPELINE_MINUTE + 30) % 60, timezone="UTC"),
        id="news_enrichment",
        name="News Coverage Enrichment",
        misfire_grace_time=600,
    )

    scheduler.add_job(
        run_financial_enrichment_job,
        CronTrigger(hour=PIPELINE_HOUR, minute=(PIPELINE_MINUTE + 45) % 60, timezone="UTC"),
        id="financial_enrichment",
        name="Financial Metrics Enrichment",
        misfire_grace_time=600,
    )

    scheduler.add_job(
        run_llm_classification_job,
        CronTrigger(hour=PIPELINE_HOUR + 1, minute=0, timezone="UTC"),
        id="llm_classification",
        name="LLM Classification",
        misfire_grace_time=600,
    )

    # Daily digest
    scheduler.add_job(
        run_digest_job,
        CronTrigger(hour=DIGEST_HOUR, minute=DIGEST_MINUTE, timezone="UTC"),
        id="digest",
        name="Email Digest",
        misfire_grace_time=300,
    )

    # Graceful shutdown
    def _shutdown(signum, frame):
        log.info("Signal %d received — shutting down scheduler", signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    log.info("Scheduler started. Jobs:")
    for job in scheduler.get_jobs():
        log.info("  %-30s %s", job.name, job.trigger)

    scheduler.start()


def run_once(tickers: list[str] | None = None, skip_enrichment: bool = False) -> None:
    """Run all jobs once immediately (for testing or manual trigger)."""
    run_pipeline_job(tickers)
    if not skip_enrichment:
        run_news_enrichment_job()
        run_financial_enrichment_job()
        run_llm_classification_job()
    log.info("One-shot run complete.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Load .env if present
    env_path = pathlib.Path(".env")
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
        except ImportError:
            pass

    parser = argparse.ArgumentParser(description="EDGAR Monitor Scheduler")
    parser.add_argument("--once",   action="store_true", help="Run once immediately and exit")
    parser.add_argument("--ticker", help="Single ticker (default: full watchlist)")
    parser.add_argument("--tickers", nargs="+", help="Multiple tickers")
    parser.add_argument("--cron",   help="Override cron schedule (e.g. '0 8 * * 1-5')")
    parser.add_argument("--skip-enrichment", action="store_true", help="Skip news/financial enrichment")
    args = parser.parse_args()

    if args.ticker:
        tickers = [args.ticker.upper()]
    elif args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        tickers = None

    if args.once:
        run_once(tickers, skip_enrichment=args.skip_enrichment)
    else:
        start_scheduler(tickers, cron_override=args.cron)
