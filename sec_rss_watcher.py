"""
sec_rss_watcher.py — Real-Time SEC EDGAR Filing Watcher

Polls the SEC EDGAR RSS feeds to detect new 10-K and 10-Q filings
as soon as they are posted, then triggers the pipeline automatically.

SEC EDGAR RSS feeds (no auth required):
  https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=10-K&dateb=&owner=include&count=40&output=atom
  https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=10-Q&dateb=&owner=include&count=40&output=atom

Workflow:
  1. Poll RSS every N minutes (default: 15)
  2. Parse new entries not seen before
  3. Filter to watchlist tickers
  4. Trigger run_pipeline.py for matched filings
  5. Optionally send an instant email alert

Usage:
    python sec_rss_watcher.py                    # poll indefinitely
    python sec_rss_watcher.py --interval 10      # every 10 minutes
    python sec_rss_watcher.py --once             # check once and exit
    python sec_rss_watcher.py --form 10-K        # only annual reports
"""
from __future__ import annotations
import argparse
import hashlib
import json
import logging
import pathlib
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

import requests

log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
RSS_BASE = "https://www.sec.gov/cgi-bin/browse-edgar"
HEADERS  = {"User-Agent": "Krish Patel patelkrish1717@gmail.com"}
SEEN_PATH = pathlib.Path("data/rss_seen.json")
DEFAULT_INTERVAL_MIN = 15

RSS_URLS = {
    "10-K": f"{RSS_BASE}?action=getcurrent&type=10-K&dateb=&owner=include&count=40&output=atom",
    "10-Q": f"{RSS_BASE}?action=getcurrent&type=10-Q&dateb=&owner=include&count=40&output=atom",
}

# XML namespaces used in SEC Atom feeds
NS = {
    "atom":  "http://www.w3.org/2005/Atom",
    "edgar": "http://www.sec.gov/Archives/edgar",
}


# ── Seen-set persistence ───────────────────────────────────────────────────────

def _load_seen() -> set[str]:
    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SEEN_PATH.exists():
        try:
            return set(json.loads(SEEN_PATH.read_text()))
        except Exception:
            pass
    return set()


def _save_seen(seen: set[str]) -> None:
    # Keep only the 2000 most recent IDs to bound file size
    items = list(seen)[-2000:]
    SEEN_PATH.write_text(json.dumps(items))


# ── RSS parsing ────────────────────────────────────────────────────────────────

def _entry_id(entry: ET.Element) -> str:
    """Stable ID for an RSS entry."""
    id_el = entry.find("atom:id", NS)
    raw   = id_el.text if id_el is not None else str(entry)
    return hashlib.md5(raw.encode()).hexdigest()


def fetch_rss(form_type: str) -> list[dict]:
    """
    Fetch and parse the SEC EDGAR RSS feed for the given form type.
    Returns list of dicts: {id, ticker, cik, form, filed, title, url}
    """
    url = RSS_URLS.get(form_type)
    if not url:
        raise ValueError(f"Unknown form type: {form_type}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("RSS fetch failed for %s: %s", form_type, e)
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        log.warning("RSS parse error: %s", e)
        return []

    entries = []
    for entry in root.findall("atom:entry", NS):
        title_el   = entry.find("atom:title",   NS)
        updated_el = entry.find("atom:updated", NS)
        link_el    = entry.find("atom:link",    NS)

        title   = title_el.text   if title_el   is not None else ""
        updated = updated_el.text if updated_el is not None else ""
        url_val = link_el.get("href", "") if link_el is not None else ""

        # Parse CIK from the entry content
        content_el = entry.find("atom:content", NS)
        content    = content_el.text if content_el is not None else ""

        # Extract ticker from title like "AAPL (0000320193) (10-K)"
        ticker = ""
        cik    = ""
        import re
        ticker_match = re.search(r"^([A-Z]{1,5})\s*\(", title or "")
        cik_match    = re.search(r"\((\d{10})\)", title or "")
        if ticker_match:
            ticker = ticker_match.group(1)
        if cik_match:
            cik = cik_match.group(1)

        filed = updated[:10] if updated else ""

        entries.append({
            "id":     _entry_id(entry),
            "ticker": ticker,
            "cik":    cik,
            "form":   form_type,
            "filed":  filed,
            "title":  title or "",
            "url":    url_val,
        })

    log.debug("Fetched %d entries from %s RSS", len(entries), form_type)
    return entries


# ── Watchlist filtering ────────────────────────────────────────────────────────

def _load_watchlist_tickers() -> set[str]:
    try:
        from watchlist import WATCHLIST
        return {w["ticker"] for w in WATCHLIST}
    except ImportError:
        return set()


def filter_to_watchlist(entries: list[dict], watchlist: set[str]) -> list[dict]:
    """Return only entries whose ticker is in the watchlist."""
    if not watchlist:
        return entries  # no filter if watchlist unavailable
    return [e for e in entries if e["ticker"] in watchlist]


# ── Pipeline trigger ───────────────────────────────────────────────────────────

def trigger_pipeline(ticker: str) -> bool:
    """Spawn run_pipeline.py for a single ticker."""
    import subprocess
    log.info("▶ Triggering pipeline for %s", ticker)
    result = subprocess.run(
        [sys.executable, "run_pipeline.py", "--ticker", ticker],
        capture_output=True, text=True,
        cwd=pathlib.Path(__file__).parent,
        timeout=600,
    )
    if result.returncode == 0:
        log.info("✓ Pipeline complete for %s", ticker)
        return True
    else:
        log.error("✗ Pipeline failed for %s: %s", ticker, result.stderr[-500:])
        return False


# ── Main poll loop ─────────────────────────────────────────────────────────────

def poll(
    form_types: list[str] = ("10-K", "10-Q"),
    interval_min: int = DEFAULT_INTERVAL_MIN,
    run_once: bool = False,
    auto_trigger: bool = True,
    log_path: Optional[pathlib.Path] = None,
) -> None:
    """
    Main polling loop. Checks SEC RSS feeds every `interval_min` minutes.
    New filings that match the watchlist are logged and optionally trigger the pipeline.
    """
    seen    = _load_seen()
    watchlist = _load_watchlist_tickers()
    new_log: list[dict] = []

    if log_path:
        log_path = pathlib.Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

    log.info("SEC RSS watcher started. Watching %d tickers, polling every %d min",
             len(watchlist), interval_min)

    while True:
        log.info("─── Polling SEC RSS at %s ───", datetime.now(timezone.utc).isoformat())
        triggered: list[str] = []

        for form in form_types:
            entries = fetch_rss(form)
            matched = filter_to_watchlist(entries, watchlist)

            for entry in matched:
                if entry["id"] in seen:
                    continue  # already processed

                seen.add(entry["id"])
                log.info(
                    "🆕 New %s filing: %s (%s) — %s",
                    entry["form"], entry["ticker"], entry["cik"], entry["title"][:80],
                )

                new_log.append({**entry, "detected_at": datetime.utcnow().isoformat()})
                if log_path:
                    log_path.write_text(json.dumps(new_log, indent=2))

                if auto_trigger and entry["ticker"] and entry["ticker"] not in triggered:
                    trigger_pipeline(entry["ticker"])
                    triggered.append(entry["ticker"])

            time.sleep(1)  # be polite between form-type requests

        _save_seen(seen)

        if run_once:
            log.info("One-shot complete. %d new filings detected.", len(new_log))
            break

        log.info("Next poll in %d minutes.", interval_min)
        time.sleep(interval_min * 60)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="SEC EDGAR RSS filing watcher")
    parser.add_argument("--interval",     type=int, default=DEFAULT_INTERVAL_MIN,
                        help="Poll interval in minutes")
    parser.add_argument("--once",         action="store_true", help="Check once and exit")
    parser.add_argument("--form",         choices=["10-K", "10-Q", "both"], default="both")
    parser.add_argument("--no-trigger",   action="store_true",
                        help="Log new filings but don't trigger pipeline")
    parser.add_argument("--log",          help="Path to write detected filings JSON log")
    args = parser.parse_args()

    forms = ["10-K", "10-Q"] if args.form == "both" else [args.form]
    poll(
        form_types=forms,
        interval_min=args.interval,
        run_once=args.once,
        auto_trigger=not args.no_trigger,
        log_path=args.log,
    )
