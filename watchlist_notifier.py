"""
watchlist_notifier.py — Watchlist monitoring loop combining SEC + news monitoring

Combines:
  - SEC RSS polling (via sec_rss_monitor.parse_feed)
  - Google News RSS fetching per ticker
  - news_importance_scorer for news signal quality
  - NotificationDispatcher for multi-channel alerts

State persistence:
  - data/watchlist.json        — list of {ticker, company, notify_threshold, email}
  - data/monitor_state.json    — last alert times, last poll times
  - data/sent_notifications.json — dedup ledger (managed by NotificationDispatcher)

Usage:
  python watchlist_notifier.py --config config/notifier_config.json
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from notifier import Notification, NotificationDispatcher, load_config
from news_importance_scorer import score_feed, is_feed_important, FeedScore
from sec_rss_monitor import (
    TickerResolver, SeenTracker, parse_feed as parse_sec_feed,
    _fetch_feed, FEED_URLS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_WATCHLIST_PATH   = Path("data/watchlist.json")
_STATE_PATH       = Path("data/monitor_state.json")
_NEWS_DEDUP_HOURS = 6   # don't resend news alert for same ticker within 6h

# Google News RSS  (no API key required, public feed)
_GNEWS_URL = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"


# ---------------------------------------------------------------------------
# Watchlist entry
# ---------------------------------------------------------------------------

def load_watchlist(path: Path = _WATCHLIST_PATH) -> list:
    """Load watchlist from JSON file.

    Expected format:
    [
      {"ticker": "NVDA", "company": "NVIDIA Corp", "notify_threshold": "HIGH", "email": "user@example.com"},
      ...
    ]
    Falls back to a minimal default if file absent.
    """
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception as exc:
            logger.error("Failed to load watchlist: %s", exc)
    return [
        {"ticker": "NVDA", "company": "NVIDIA Corp",    "notify_threshold": "MEDIUM", "email": ""},
        {"ticker": "AAPL", "company": "Apple Inc",      "notify_threshold": "HIGH",   "email": ""},
        {"ticker": "MSFT", "company": "Microsoft Corp", "notify_threshold": "MEDIUM", "email": ""},
        {"ticker": "JPM",  "company": "JPMorgan Chase", "notify_threshold": "HIGH",   "email": ""},
    ]


# ---------------------------------------------------------------------------
# State manager
# ---------------------------------------------------------------------------

class MonitorState:
    """Persists per-ticker last-alert timestamps and other monitor state."""

    def __init__(self, path: Path = _STATE_PATH):
        self._path = path
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except Exception:
                return {}
        return {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2))

    def get_last_news_alert(self, ticker: str) -> Optional[datetime]:
        ts = self._data.get(f"news_alert:{ticker}")
        if ts:
            try:
                return datetime.fromisoformat(ts)
            except Exception:
                return None
        return None

    def set_last_news_alert(self, ticker: str) -> None:
        self._data[f"news_alert:{ticker}"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def get_last_sec_alert(self, ticker: str) -> Optional[datetime]:
        ts = self._data.get(f"sec_alert:{ticker}")
        if ts:
            try:
                return datetime.fromisoformat(ts)
            except Exception:
                return None
        return None

    def set_last_sec_alert(self, ticker: str) -> None:
        self._data[f"sec_alert:{ticker}"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def is_news_alert_throttled(self, ticker: str, hours: int = _NEWS_DEDUP_HOURS) -> bool:
        last = self.get_last_news_alert(ticker)
        if last is None:
            return False
        now = datetime.now(timezone.utc)
        # Ensure timezone-aware comparison
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return (now - last) < timedelta(hours=hours)


# ---------------------------------------------------------------------------
# Google News fetcher
# ---------------------------------------------------------------------------

def fetch_google_news(ticker: str, company: str = "", max_articles: int = 20) -> list:
    """Fetch Google News RSS for a ticker, return list of article dicts."""
    query = ticker
    if company:
        query = f"{ticker} {company}"
    url = _GNEWS_URL.format(query=urllib.parse.quote(query))  # type: ignore[attr-defined]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "edgar-monitor/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_bytes = resp.read()
    except Exception as exc:
        logger.warning("Google News fetch failed for %s: %s", ticker, exc)
        return []

    articles = []
    try:
        root = ET.fromstring(xml_bytes)
        channel = root.find("channel")
        if channel is None:
            return []
        for item in list(channel.findall("item"))[:max_articles]:
            title_el = item.find("title")
            desc_el  = item.find("description")
            link_el  = item.find("link")
            articles.append({
                "title": title_el.text.strip() if title_el is not None and title_el.text else "",
                "body":  desc_el.text.strip()  if desc_el  is not None and desc_el.text  else "",
                "url":   link_el.text.strip()  if link_el  is not None and link_el.text  else "",
            })
    except ET.ParseError as exc:
        logger.warning("XML parse error for %s news: %s", ticker, exc)
    return articles


# ---------------------------------------------------------------------------
# Per-ticker alert logic
# ---------------------------------------------------------------------------

_THRESHOLD_MAP = {"CRITICAL": 80, "HIGH": 60, "MEDIUM": 40, "LOW": 20}


def process_ticker_news(
    entry: dict,
    state: MonitorState,
    dispatcher: NotificationDispatcher,
    sec_just_filed: bool = False,
    sec_notif: Optional[Notification] = None,
) -> None:
    """Fetch + score news for one watchlist entry; dispatch alert if warranted."""
    ticker  = entry["ticker"]
    company = entry.get("company", "")
    threshold_name = entry.get("notify_threshold", "MEDIUM")

    if state.is_news_alert_throttled(ticker):
        logger.debug("%s news alert throttled (within %dh window)", ticker, _NEWS_DEDUP_HOURS)
        return

    articles = fetch_google_news(ticker, company)
    if not articles:
        logger.debug("No news articles fetched for %s", ticker)
        return

    feed_score: FeedScore = score_feed(articles)
    important  = is_feed_important(feed_score)

    logger.info(
        "%s news: %d articles  composite=%.2f  quality=%.2f  top=%s  important=%s",
        ticker, feed_score.n_articles, feed_score.composite_score,
        feed_score.quality_score, feed_score.top_bucket, important
    )

    if not important:
        return

    # If a SEC filing alert was just sent, send a combined alert instead
    if sec_just_filed and sec_notif is not None:
        combined_notif = Notification(
            ticker=sec_notif.ticker,
            title=f"{ticker} {sec_notif.top_bucket} filing + {feed_score.top_bucket} news coverage",
            body=(f"SEC filing filed. News score: composite={feed_score.composite_score:.2f}, "
                  f"quality={feed_score.quality_score:.2f}. "
                  f"Top news bucket: {feed_score.top_bucket} ({feed_score.bucket_counts.get(feed_score.top_bucket, 0)} articles)."),
            severity="",
            source="COMBINED",
            materiality_score=sec_notif.materiality_score,
            news_quality_score=feed_score.quality_score,
            attention_gap=max(sec_notif.attention_gap, feed_score.composite_score * 100),
            url=sec_notif.url,
            filed_at=sec_notif.filed_at,
            sentiment="BEARISH" if feed_score.quality_score > 0.6 else "NEUTRAL",
            top_bucket=feed_score.top_bucket,
            accession=sec_notif.accession + ":combined",
        )
        result = dispatcher.dispatch(combined_notif)
        if result:
            state.set_last_news_alert(ticker)
            state.set_last_sec_alert(ticker)
        return

    # Standalone news alert
    url = articles[0].get("url", "") if articles else ""
    gap = feed_score.composite_score * 100   # scale to 0-100 like attention_gap

    news_notif = Notification(
        ticker=ticker,
        title=(f"{ticker} — {feed_score.top_bucket} news signal "
               f"(quality={feed_score.quality_score:.2f})"),
        body=(f"{feed_score.n_articles} recent articles scored. "
              f"Composite: {feed_score.composite_score:.2f}. "
              f"Top bucket: {feed_score.top_bucket} "
              f"({feed_score.bucket_counts.get(feed_score.top_bucket, 0)} articles). "
              f"Quality score: {feed_score.quality_score:.2f}."),
        severity="",
        source="NEWS",
        materiality_score=0.0,
        news_quality_score=feed_score.quality_score,
        attention_gap=gap,
        url=url,
        filed_at=datetime.now(timezone.utc).isoformat(),
        sentiment="BEARISH" if feed_score.quality_score > 0.6 else "NEUTRAL",
        top_bucket=feed_score.top_bucket,
        accession=f"news:{ticker}:{datetime.now(timezone.utc).strftime('%Y%m%d%H')}",
    )
    result = dispatcher.dispatch(news_notif)
    if result:
        state.set_last_news_alert(ticker)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run(config_path: str = "config/notifier_config.json", poll_interval: int = 300) -> None:
    cfg        = load_config(config_path)
    dispatcher = NotificationDispatcher(cfg)
    resolver   = TickerResolver()
    sec_tracker = SeenTracker()
    state      = MonitorState()
    watchlist  = load_watchlist()
    watchset   = {e["ticker"].upper(): e for e in watchlist}

    logger.info("Watchlist notifier started — %d tickers", len(watchset))

    try:
        while True:
            # ── SEC RSS polling ──────────────────────────────────────────
            new_sec_filings: dict = {}   # ticker → Notification

            for form_type, url in FEED_URLS.items():
                try:
                    xml_bytes = _fetch_feed(url)
                except Exception as exc:
                    logger.error("SEC feed error: %s", exc)
                    continue

                entries = parse_sec_feed(xml_bytes, form_type, resolver)
                for fe in entries:
                    if sec_tracker.is_seen(fe.accession):
                        continue
                    sec_tracker.mark(fe.accession)

                    ticker = fe.ticker.upper() if fe.ticker else ""
                    if ticker not in watchset:
                        continue

                    logger.info("New SEC filing: %s %s (%s)", ticker, form_type, fe.accession)

                    attention_gap    = 50.0
                    materiality      = 0.5
                    news_quality     = 0.5
                    sentiment        = "NEUTRAL"
                    top_bucket       = "EARNINGS"

                    try:
                        import filing_pipeline  # type: ignore
                        result = filing_pipeline.run_filing_comparison(ticker)
                        if result:
                            attention_gap = result.get("attention_gap", attention_gap)
                            materiality   = result.get("materiality_score", materiality)
                            news_quality  = result.get("news_quality_score", news_quality)
                            sentiment     = result.get("sentiment", sentiment)
                            top_bucket    = result.get("top_bucket", top_bucket)
                    except ImportError:
                        pass

                    sec_notif = Notification(
                        ticker=ticker,
                        title=f"{ticker} files {form_type} (gap {attention_gap:.0f})",
                        body=(f"{fe.company} filed a {form_type}. "
                              f"Attention gap: {attention_gap:.1f}."),
                        severity="",
                        source="SEC_FILING",
                        materiality_score=materiality,
                        news_quality_score=news_quality,
                        attention_gap=attention_gap,
                        url=fe.filing_url,
                        filed_at=fe.filed_at,
                        sentiment=sentiment,
                        top_bucket=top_bucket,
                        accession=fe.accession,
                    )
                    result = dispatcher.dispatch(sec_notif)
                    if result:
                        state.set_last_sec_alert(ticker)
                        new_sec_filings[ticker] = sec_notif

            # ── News monitoring for each watchlist ticker ────────────────
            for ticker, entry in watchset.items():
                sec_just_filed = ticker in new_sec_filings
                sec_notif      = new_sec_filings.get(ticker)
                try:
                    process_ticker_news(entry, state, dispatcher, sec_just_filed, sec_notif)
                except Exception as exc:
                    logger.error("News processing error for %s: %s", ticker, exc)

            logger.info("Cycle complete — sleeping %ds", poll_interval)
            time.sleep(poll_interval)

    except KeyboardInterrupt:
        logger.info("Watchlist notifier stopped (Ctrl+C).")


# ---------------------------------------------------------------------------
# Minimal urllib.parse shim (in case import is missing at module level)
# ---------------------------------------------------------------------------

import urllib.parse  # noqa: E402  (already in stdlib, just ensuring it's imported)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Watchlist monitoring loop (SEC + News).")
    parser.add_argument("--config", default="config/notifier_config.json",
                        help="Path to notifier_config.json")
    parser.add_argument("--interval", type=int, default=300,
                        help="Poll interval in seconds (default 300)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")

    # Quick smoke-test: load watchlist and show it
    wl = load_watchlist()
    print(f"Watchlist ({len(wl)} tickers):")
    for e in wl:
        print(f"  {e['ticker']:6s}  {e.get('company',''):30s}  threshold={e.get('notify_threshold','MEDIUM')}")
    print()

    run(config_path=args.config, poll_interval=args.interval)
