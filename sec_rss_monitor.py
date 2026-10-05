"""
sec_rss_monitor.py — Real-time EDGAR RSS poller for 10-K and 10-Q filings

Polls SEC EDGAR Atom feeds every 300 seconds (configurable).
For each new filing on the watchlist:
  1. Compares CIK → ticker using a cached lookup
  2. Checks if accession was already seen (data/seen_filings.json)
  3. Dispatches a Notification if attention_gap exceeds threshold

Usage:
  python sec_rss_monitor.py --watchlist NVDA AAPL MSFT JPM --interval 300
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# SEC EDGAR Atom feed URLs
FEED_URLS = {
    "10-K": (
        "https://www.sec.gov/cgi-bin/browse-edgar"
        "?action=getcurrent&type=10-K&dateb=&owner=include"
        "&count=40&search_text=&output=atom"
    ),
    "10-Q": (
        "https://www.sec.gov/cgi-bin/browse-edgar"
        "?action=getcurrent&type=10-Q&dateb=&owner=include"
        "&count=40&search_text=&output=atom"
    ),
}

# Atom XML namespace
_ATOM_NS = "http://www.w3.org/2005/Atom"

# CIK → ticker mapping (bootstrap from SEC company_tickers.json)
_CIK_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"

# Paths for persistent state
_SEEN_PATH   = Path("data/seen_filings.json")
_TICKER_CACHE = Path("data/ticker_cache.json")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class FilingEntry:
    accession: str
    company:   str
    cik:       str
    ticker:    str
    form_type: str
    filed_at:  str
    filing_url: str


# ---------------------------------------------------------------------------
# CIK → Ticker resolver
# ---------------------------------------------------------------------------

class TickerResolver:
    """Resolves company names / CIK numbers to ticker symbols.

    Uses SEC's company_tickers.json; result cached in data/ticker_cache.json.
    """

    def __init__(self, cache_path: Path = _TICKER_CACHE):
        self._cache_path = cache_path
        self._cik_to_ticker: dict = {}
        self._name_to_ticker: dict = {}
        self._load_cache()

    def _load_cache(self) -> None:
        if self._cache_path.exists():
            try:
                raw = json.loads(self._cache_path.read_text())
                self._cik_to_ticker  = raw.get("cik", {})
                self._name_to_ticker = raw.get("name", {})
                logger.debug("Ticker cache loaded: %d entries", len(self._cik_to_ticker))
                return
            except Exception:
                pass
        self._refresh()

    def _refresh(self) -> None:
        """Download fresh CIK → ticker mapping from SEC."""
        logger.info("Downloading ticker cache from SEC …")
        try:
            req = urllib.request.Request(_CIK_TICKER_URL,
                                         headers={"User-Agent": "edgar-monitor contact@example.com"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            for entry in data.values():
                cik    = str(entry["cik_str"]).zfill(10)
                ticker = entry["ticker"].upper()
                name   = entry["title"].upper()
                self._cik_to_ticker[cik]  = ticker
                self._name_to_ticker[name] = ticker
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps(
                {"cik": self._cik_to_ticker, "name": self._name_to_ticker}, indent=2
            ))
            logger.info("Ticker cache saved: %d CIKs", len(self._cik_to_ticker))
        except Exception as exc:
            logger.error("Failed to refresh ticker cache: %s", exc)

    def resolve_cik(self, cik: str) -> Optional[str]:
        padded = cik.zfill(10)
        return self._cik_to_ticker.get(padded)

    def resolve_name(self, name: str) -> Optional[str]:
        return self._name_to_ticker.get(name.upper())

    def resolve(self, cik: str = "", name: str = "") -> Optional[str]:
        return self.resolve_cik(cik) or self.resolve_name(name)


# ---------------------------------------------------------------------------
# Seen-filing tracker
# ---------------------------------------------------------------------------

class SeenTracker:
    """Tracks accession numbers already processed so duplicates are skipped."""

    def __init__(self, path: Path = _SEEN_PATH):
        self._path = path
        self._seen: set = set()
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._seen = set(json.loads(self._path.read_text()))
            except Exception:
                self._seen = set()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(sorted(self._seen), indent=2))

    def is_seen(self, accession: str) -> bool:
        return accession in self._seen

    def mark(self, accession: str) -> None:
        self._seen.add(accession)
        self._save()


# ---------------------------------------------------------------------------
# Atom feed parser
# ---------------------------------------------------------------------------

def _fetch_feed(url: str) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": "edgar-monitor contact@example.com"}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def parse_feed(xml_bytes: bytes, form_type: str, resolver: TickerResolver) -> list:
    """Parse EDGAR Atom feed XML into a list of FilingEntry objects."""
    entries = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        logger.error("XML parse error: %s", exc)
        return entries

    for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
        def text(tag: str) -> str:
            el = entry.find(f"{{{_ATOM_NS}}}{tag}")
            return el.text.strip() if el is not None and el.text else ""

        title       = text("title")   # e.g. "10-K - NVIDIA CORP (0001045810) …"
        filing_url  = ""
        link_el     = entry.find(f"{{{_ATOM_NS}}}link")
        if link_el is not None:
            filing_url = link_el.get("href", "")

        filed_at = text("updated") or text("published")

        # Extract CIK and company from title: "FORM - COMPANY NAME (CIK) …"
        cik = ""
        company = ""
        import re
        m = re.search(r"\((\d+)\)", title)
        if m:
            cik = m.group(1)
        # Company name is between form type and the CIK paren
        m2 = re.match(r"[\w-]+\s+-\s+(.+?)\s+\(\d+\)", title)
        if m2:
            company = m2.group(1).strip()

        ticker = resolver.resolve(cik=cik, name=company) or ""

        # Accession from filing URL
        acc = ""
        m3 = re.search(r"(\d{10}-\d{2}-\d{6})", filing_url)
        if m3:
            acc = m3.group(1)

        if acc:
            entries.append(FilingEntry(
                accession=acc,
                company=company,
                cik=cik,
                ticker=ticker,
                form_type=form_type,
                filed_at=filed_at,
                filing_url=filing_url,
            ))

    return entries


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------

def run_monitor(
    watchlist: list,
    poll_interval: int = 300,
    notifier_config: Optional[dict] = None,
    attention_gap_threshold: float = 40.0,
) -> None:
    """Infinite loop polling EDGAR RSS for new 10-K / 10-Q filings.

    For each new filing on the watchlist:
      - Logs the discovery
      - Attempts to import filing_pipeline and run comparison
      - Dispatches a Notification if gap >= threshold

    Args:
        watchlist: list of ticker symbols to monitor, e.g. ["NVDA", "AAPL"]
        poll_interval: seconds between polls (default 300)
        notifier_config: dict passed to NotificationDispatcher
        attention_gap_threshold: minimum gap to trigger notification
    """
    from notifier import NotificationDispatcher, Notification, load_config

    cfg = notifier_config or load_config()
    dispatcher = NotificationDispatcher(cfg)
    resolver   = TickerResolver()
    tracker    = SeenTracker()
    watchset   = {t.upper() for t in watchlist}

    logger.info("SEC RSS monitor started — watchlist: %s", sorted(watchset))
    logger.info("Poll interval: %ds  |  Gap threshold: %.0f", poll_interval, attention_gap_threshold)

    try:
        while True:
            for form_type, url in FEED_URLS.items():
                logger.debug("Polling %s feed …", form_type)
                try:
                    xml_bytes = _fetch_feed(url)
                except Exception as exc:
                    logger.error("Feed fetch error (%s): %s", form_type, exc)
                    continue

                entries = parse_feed(xml_bytes, form_type, resolver)
                logger.debug("Parsed %d entries from %s feed", len(entries), form_type)

                for entry in entries:
                    if tracker.is_seen(entry.accession):
                        continue
                    tracker.mark(entry.accession)

                    if not entry.ticker or entry.ticker not in watchset:
                        continue

                    logger.info(
                        "NEW %s filing: %s (%s) — %s",
                        entry.form_type, entry.ticker, entry.company, entry.accession
                    )

                    # Attempt to run filing comparison pipeline
                    attention_gap    = 50.0   # default if pipeline unavailable
                    materiality      = 0.5
                    news_quality     = 0.5
                    sentiment        = "NEUTRAL"
                    top_bucket       = "EARNINGS"

                    try:
                        import filing_pipeline  # type: ignore
                        result = filing_pipeline.run_filing_comparison(entry.ticker)
                        if result:
                            attention_gap = result.get("attention_gap", attention_gap)
                            materiality   = result.get("materiality_score", materiality)
                            news_quality  = result.get("news_quality_score", news_quality)
                            sentiment     = result.get("sentiment", sentiment)
                            top_bucket    = result.get("top_bucket", top_bucket)
                    except ImportError:
                        logger.debug("filing_pipeline not available — using default scores")
                    except Exception as exc:
                        logger.error("Pipeline error for %s: %s", entry.ticker, exc)

                    if attention_gap < attention_gap_threshold:
                        logger.info(
                            "Gap %.1f < threshold %.1f for %s — no alert",
                            attention_gap, attention_gap_threshold, entry.ticker
                        )
                        continue

                    notif = Notification(
                        ticker=entry.ticker,
                        title=(f"{entry.ticker} files {entry.form_type} "
                               f"(attention gap {attention_gap:.0f})"),
                        body=(f"{entry.company} filed a {entry.form_type} on {entry.filed_at[:10]}. "
                              f"Attention gap vs analyst coverage: {attention_gap:.1f} points."),
                        severity="",
                        source="SEC_FILING",
                        materiality_score=materiality,
                        news_quality_score=news_quality,
                        attention_gap=attention_gap,
                        url=entry.filing_url,
                        filed_at=entry.filed_at,
                        sentiment=sentiment,
                        top_bucket=top_bucket,
                        accession=entry.accession,
                    )
                    dispatcher.dispatch(notif)

            logger.info("Sleeping %ds until next poll …", poll_interval)
            time.sleep(poll_interval)

    except KeyboardInterrupt:
        logger.info("Monitor stopped by user (Ctrl+C).")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Poll EDGAR RSS for new 10-K / 10-Q filings.")
    p.add_argument("--watchlist", nargs="+", default=["NVDA", "AAPL", "MSFT", "JPM"],
                   help="Space-separated ticker symbols to monitor")
    p.add_argument("--interval", type=int, default=300,
                   help="Poll interval in seconds (default: 300)")
    p.add_argument("--threshold", type=float, default=40.0,
                   help="Minimum attention gap to trigger a notification (default: 40)")
    p.add_argument("--config", default="config/notifier_config.json",
                   help="Path to notifier_config.json")
    p.add_argument("--verbose", action="store_true", help="Enable DEBUG logging")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")

    # Quick smoke-test: fetch + parse one feed entry
    print("Smoke test: fetching 10-K feed …")
    resolver = TickerResolver()
    try:
        xml_bytes = _fetch_feed(FEED_URLS["10-K"])
        entries   = parse_feed(xml_bytes, "10-K", resolver)
        print(f"  Parsed {len(entries)} entries")
        for e in entries[:3]:
            print(f"  {e.form_type:5s}  {e.ticker or '(no ticker)':6s}  {e.company[:40]:40s}  {e.accession}")
    except Exception as exc:
        print(f"  Feed unavailable (offline?): {exc}")

    print(f"\nStarting monitor for {args.watchlist} (interval={args.interval}s) …")
    run_monitor(
        watchlist=args.watchlist,
        poll_interval=args.interval,
        attention_gap_threshold=args.threshold,
    )
