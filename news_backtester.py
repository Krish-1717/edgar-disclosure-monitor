"""
news_backtester.py — News Signal Backtester for EDGAR Disclosure Monitor

Fetches Google News RSS headlines for a set of tickers, pairs them with
yfinance price data, and computes forward returns per news keyword bucket.

This validates (or refutes) the signal weights in news_signal_weights.py.
Run this periodically as more data accumulates — once you have ≥50 events
per bucket, pass the results to `update_weights_from_backtest()` to tune the
classifier.

Usage:
    pip install yfinance requests
    python news_backtester.py                          # all default tickers
    python news_backtester.py --ticker AAPL NVDA       # specific tickers
    python news_backtester.py --output data/backtest_results.json
    python news_backtester.py --days 180               # look back 180 days

Output:
    JSON: {bucket: {mean_1d_return, mean_3d_return, mean_5d_return,
                    hit_rate, sharpe, n_events, events: [...]}}
    Console: formatted table with key stats
"""
from __future__ import annotations
import argparse
import json
import logging
import math
import pathlib
import statistics
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
import xml.etree.ElementTree as ET

try:
    import requests
except ImportError:
    raise SystemExit("Install requests: pip install requests")

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("Install yfinance: pip install yfinance")

from news_signal_weights import classify_headline

log = logging.getLogger(__name__)

DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "JPM", "TSLA", "META", "GOOGL", "AMZN", "NFLX", "AMD"]
FORWARD_DAYS    = [1, 3, 5]    # days after headline to measure return
RSS_URL         = "https://news.google.com/rss/search?q={query}+stock&hl=en-US&gl=US&ceid=US:en"
HEADERS         = {"User-Agent": "edgar-monitor/1.0 (research; patelkrish1717@gmail.com)"}


# ── Price data ─────────────────────────────────────────────────────────────────

def fetch_price_history(ticker: str, days: int = 120) -> dict[str, float]:
    """
    Return {date_str: close_price} for the last `days` calendar days.
    date_str format: "YYYY-MM-DD"
    """
    try:
        end   = datetime.now()
        start = end - timedelta(days=days + 30)  # extra buffer for weekends
        hist  = yf.download(ticker, start=start.strftime("%Y-%m-%d"),
                             end=end.strftime("%Y-%m-%d"), progress=False, auto_adjust=True)
        if hist.empty:
            return {}
        prices: dict[str, float] = {}
        for idx, row in hist.iterrows():
            date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
            prices[date_str] = float(row["Close"])
        return prices
    except Exception as e:
        log.warning("Price fetch failed for %s: %s", ticker, e)
        return {}


def get_forward_return(prices: dict[str, float], from_date: str, n_days: int) -> Optional[float]:
    """
    Compute forward return: (price[from_date + n_trading_days] - price[from_date]) / price[from_date]
    Returns None if price data is unavailable.
    """
    sorted_dates = sorted(prices.keys())
    try:
        idx = sorted_dates.index(from_date)
    except ValueError:
        # date not a trading day — find nearest next trading day
        candidates = [d for d in sorted_dates if d >= from_date]
        if not candidates:
            return None
        idx = sorted_dates.index(candidates[0])

    target_idx = idx + n_days
    if target_idx >= len(sorted_dates):
        return None

    p0 = prices[sorted_dates[idx]]
    p1 = prices[sorted_dates[target_idx]]
    if p0 == 0:
        return None
    return (p1 - p0) / p0


# ── News fetching ──────────────────────────────────────────────────────────────

def fetch_rss_headlines(ticker: str) -> list[dict]:
    """
    Fetch Google News RSS for a ticker.
    Returns list of {title, date} dicts.
    """
    query = ticker
    url   = RSS_URL.format(query=query)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("RSS fetch failed for %s: %s", ticker, e)
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        log.warning("RSS parse error for %s: %s", ticker, e)
        return []

    articles = []
    for item in root.findall(".//item"):
        title_el = item.find("title")
        pub_el   = item.find("pubDate")
        if title_el is None:
            continue
        title   = title_el.text or ""
        pub_raw = pub_el.text if pub_el is not None else ""
        # Parse RFC 2822 date → YYYY-MM-DD
        date_str = ""
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(pub_raw)
            date_str = dt.strftime("%Y-%m-%d")
        except Exception:
            pass
        articles.append({"title": title, "date": date_str})

    log.debug("  Fetched %d headlines for %s", len(articles), ticker)
    return articles


# ── Backtest engine ────────────────────────────────────────────────────────────

def run_backtest(
    tickers: list[str] = DEFAULT_TICKERS,
    days: int = 120,
    min_events_per_bucket: int = 3,
) -> dict:
    """
    Full backtest pipeline.

    For each ticker:
      1. Fetch price history (yfinance)
      2. Fetch headlines (Google News RSS)
      3. Classify each headline into keyword buckets
      4. Compute forward returns for the headline date
      5. Aggregate stats per bucket

    Returns
    -------
    dict: {
        bucket: {
            mean_1d_return, mean_3d_return, mean_5d_return,
            hit_rate, sharpe_1d, n_events,
            events: [{ticker, date, headline, return_1d, return_3d, buckets}]
        }
    }
    """
    all_events: list[dict] = []

    for ticker in tickers:
        log.info("Processing %s...", ticker)

        prices = fetch_price_history(ticker, days=days)
        if not prices:
            log.warning("  No price data for %s — skipping", ticker)
            continue

        headlines = fetch_rss_headlines(ticker)
        if not headlines:
            log.warning("  No headlines for %s — skipping", ticker)
            continue

        for article in headlines:
            title = article["title"]
            date  = article["date"]
            if not date:
                continue

            buckets = classify_headline(title)
            if not buckets:
                continue  # unclassifiable — skip

            r1 = get_forward_return(prices, date, 1)
            r3 = get_forward_return(prices, date, 3)
            r5 = get_forward_return(prices, date, 5)

            if r1 is None:
                continue  # no price data for this date

            all_events.append({
                "ticker":     ticker,
                "date":       date,
                "headline":   title,
                "buckets":    buckets,
                "return_1d":  round(r1, 6),
                "return_3d":  round(r3, 6) if r3 is not None else None,
                "return_5d":  round(r5, 6) if r5 is not None else None,
            })

        time.sleep(1.0)  # gentle rate limiting

    # ── Aggregate by bucket ────────────────────────────────────────────────────
    from news_signal_weights import SIGNAL_WEIGHTS
    results: dict = {}

    for bucket in SIGNAL_WEIGHTS:
        events = [e for e in all_events if bucket in e["buckets"]]
        if len(events) < min_events_per_bucket:
            results[bucket] = {"n_events": len(events), "note": "insufficient data"}
            continue

        r1s = [e["return_1d"]                         for e in events]
        r3s = [e["return_3d"] for e in events if e["return_3d"] is not None]
        r5s = [e["return_5d"] for e in events if e["return_5d"] is not None]

        mean_r1 = statistics.mean(r1s)
        hit_rate = sum(1 for r in r1s if r > 0) / len(r1s)

        def _sharpe(rets: list[float]) -> Optional[float]:
            if len(rets) < 2:
                return None
            mu  = statistics.mean(rets)
            std = statistics.stdev(rets)
            return round(mu / std, 3) if std else None

        results[bucket] = {
            "n_events":       len(events),
            "mean_1d_return": round(mean_r1, 6),
            "mean_3d_return": round(statistics.mean(r3s), 6) if r3s else None,
            "mean_5d_return": round(statistics.mean(r5s), 6) if r5s else None,
            "std_1d":         round(statistics.stdev(r1s), 6) if len(r1s) > 1 else None,
            "hit_rate":       round(hit_rate, 4),
            "sharpe_1d":      _sharpe(r1s),
            "events":         events[:20],  # store first 20 for inspection
        }

    return results


# ── Reporting ──────────────────────────────────────────────────────────────────

def print_report(results: dict) -> None:
    """Print formatted backtest summary to stdout."""
    print("\n" + "═" * 72)
    print("  EDGAR NEWS SIGNAL BACKTEST RESULTS")
    print("═" * 72)
    print(f"  {'Bucket':<14} {'N':>5} {'Mean 1d%':>10} {'Mean 3d%':>10} {'HitRate':>9} {'Sharpe':>8}")
    print("  " + "─" * 60)

    from news_signal_weights import SIGNAL_WEIGHTS
    for bucket, stats in sorted(results.items(), key=lambda x: x[1].get("n_events", 0), reverse=True):
        n = stats.get("n_events", 0)
        if n == 0 or "note" in stats:
            print(f"  {bucket:<14} {n:>5}  {'(insufficient data)'}")
            continue
        r1  = f"{stats['mean_1d_return']*100:+.3f}%" if stats.get("mean_1d_return") is not None else "—"
        r3  = f"{stats['mean_3d_return']*100:+.3f}%" if stats.get("mean_3d_return") is not None else "—"
        hit = f"{stats['hit_rate']*100:.1f}%"        if stats.get("hit_rate")        is not None else "—"
        sh  = f"{stats['sharpe_1d']:+.3f}"           if stats.get("sharpe_1d")       is not None else "—"
        prior = SIGNAL_WEIGHTS[bucket]["direction"]
        flag  = "✓" if (prior > 0 and stats["mean_1d_return"] > 0) or \
                       (prior < 0 and stats["mean_1d_return"] < 0) or prior == 0 else "⚠"
        print(f"  {bucket:<14} {n:>5}  {r1:>10}  {r3:>10}  {hit:>9}  {sh:>8}  {flag}")

    print("═" * 72)
    print("  ✓ = direction matches prior | ⚠ = consider flipping weight")
    print("  Update news_signal_weights.py if N ≥ 50 per bucket")
    print("═" * 72 + "\n")


def save_results(results: dict, path: pathlib.Path) -> None:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2))
    log.info("Backtest results saved to %s", path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="EDGAR news signal backtester")
    parser.add_argument("--ticker",  "-t", nargs="+", default=DEFAULT_TICKERS,
                        help="Tickers to backtest (default: 10 large-caps)")
    parser.add_argument("--days",    "-d", type=int, default=120,
                        help="Days of price history to fetch")
    parser.add_argument("--output",  "-o", help="Path to save JSON results")
    parser.add_argument("--min-events", type=int, default=3,
                        help="Min events to report a bucket (default: 3)")
    args = parser.parse_args()

    results = run_backtest(
        tickers=args.ticker,
        days=args.days,
        min_events_per_bucket=args.min_events,
    )
    print_report(results)

    if args.output:
        save_results(results, pathlib.Path(args.output))
        print(f"Results saved to {args.output}")
