"""
news_fetcher.py — Press Coverage Scorer for EDGAR Disclosure Monitor

Fetches press coverage for a ticker around a filing date using:
  1. RSS feeds from Reuters, MarketWatch, Seeking Alpha
  2. NewsAPI (optional, requires NEWSAPI_KEY env var)
  3. Google News RSS (no key required)

Returns a normalized_coverage score (0.0–1.0) used in the Attention Gap formula:
  Attention Gap = Materiality / max(normalized_coverage, 0.01)

Coverage scoring:
  - 0 articles  → 0.05  (near-zero, not absolute zero)
  - 1–2 articles → 0.15
  - 3–5 articles → 0.35
  - 6–10 articles → 0.60
  - 11–20 articles → 0.80
  - 20+  articles → 1.00
"""
from __future__ import annotations
import os
import time
import hashlib
import logging
import pathlib
import json
from datetime import datetime, timedelta
from urllib.parse import quote_plus, urlparse

import requests

log = logging.getLogger(__name__)

CACHE_DIR = pathlib.Path("data/news_cache")
CACHE_TTL  = 60 * 60 * 6  # 6 hours

# Coverage breakpoints → normalized score
_COVERAGE_SCALE = [
    (0,  0.05),
    (2,  0.15),
    (5,  0.35),
    (10, 0.60),
    (20, 0.80),
]

_HEADERS = {
    "User-Agent": "EDGAR-Monitor/1.0 (research; patelkrish1717@gmail.com)",
    "Accept":     "application/rss+xml, application/xml, text/xml, */*",
}

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")


def _cache_key(ticker: str, date: str) -> pathlib.Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5(f"{ticker}:{date}".encode()).hexdigest()
    return CACHE_DIR / f"{key}.json"


def _load_cache(ticker: str, date: str) -> dict | None:
    path = _cache_key(ticker, date)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if time.time() - data.get("ts", 0) < CACHE_TTL:
            return data
    except Exception:
        pass
    return None


def _save_cache(ticker: str, date: str, result: dict) -> None:
    path = _cache_key(ticker, date)
    result["ts"] = time.time()
    path.write_text(json.dumps(result))


def _fetch_google_news_rss(query: str, window_days: int = 3) -> list[dict]:
    """Fetch articles from Google News RSS for a search query."""
    encoded = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        log.warning("Google News RSS error for %r: %s", query, e)
        return []

    # Parse RSS with xml.etree (no external dep)
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        log.warning("RSS parse error: %s", e)
        return []

    articles = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        link = (item.findtext("link") or "").strip()
        articles.append({"title": title, "pub_date": pub_date, "url": link})
    return articles


def _fetch_newsapi(ticker: str, company_name: str, filed_date: str, window_days: int = 3) -> list[dict]:
    """Fetch from NewsAPI (requires NEWSAPI_KEY env var)."""
    if not NEWSAPI_KEY:
        return []
    try:
        dt = datetime.strptime(filed_date, "%Y-%m-%d")
    except ValueError:
        return []

    from_dt = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    to_dt   = (dt + timedelta(days=window_days)).strftime("%Y-%m-%d")

    url = "https://newsapi.org/v2/everything"
    params = {
        "q":         f'"{ticker}" OR "{company_name}"',
        "from":      from_dt,
        "to":        to_dt,
        "sortBy":    "relevancy",
        "language":  "en",
        "pageSize":  50,
        "apiKey":    NEWSAPI_KEY,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("articles", [])
    except Exception as e:
        log.warning("NewsAPI error for %s: %s", ticker, e)
        return []


def _normalize_score(article_count: int) -> float:
    """Map article count to 0.0–1.0 coverage score."""
    score = 1.0
    for threshold, val in _COVERAGE_SCALE:
        if article_count <= threshold:
            score = val
            break
    else:
        score = 1.0
    return round(score, 3)


def _filter_by_date_window(articles: list[dict], filed_date: str, window_days: int = 3) -> list[dict]:
    """Keep only articles published within ±window_days of the filing date."""
    try:
        filed_dt = datetime.strptime(filed_date, "%Y-%m-%d")
    except ValueError:
        return articles  # can't filter, return all

    low  = filed_dt - timedelta(days=1)
    high = filed_dt + timedelta(days=window_days)

    filtered = []
    for a in articles:
        raw = a.get("pub_date") or a.get("publishedAt") or ""
        for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw[:len(fmt) + 5].strip(), fmt).replace(tzinfo=None)
                if low <= dt <= high:
                    filtered.append(a)
                break
            except ValueError:
                continue
    return filtered if filtered else articles  # fallback: return all if none matched


def get_coverage_score(
    ticker: str,
    company_name: str,
    filed_date: str,
    window_days: int = 3,
    use_cache: bool = True,
) -> tuple[float, int]:
    """
    Return (normalized_coverage_score, article_count) for a ticker around a filing date.

    Parameters
    ----------
    ticker        : e.g. "AAPL"
    company_name  : e.g. "Apple Inc."
    filed_date    : ISO string "YYYY-MM-DD"
    window_days   : days after filing to scan
    use_cache     : whether to use disk cache

    Returns
    -------
    (score 0.0–1.0, raw article count)
    """
    if use_cache:
        cached = _load_cache(ticker, filed_date)
        if cached:
            return cached["score"], cached["count"]

    articles: list[dict] = []

    # 1. Google News RSS — free, no key
    query = f"{ticker} SEC filing 10-K 10-Q earnings"
    gn_articles = _fetch_google_news_rss(query, window_days)
    articles.extend(_filter_by_date_window(gn_articles, filed_date, window_days))

    # 2. Company name search
    company_query = f'"{company_name}" annual report quarterly earnings disclosure'
    company_articles = _fetch_google_news_rss(company_query, window_days)
    articles.extend(_filter_by_date_window(company_articles, filed_date, window_days))

    # 3. NewsAPI (if key available)
    na_articles = _fetch_newsapi(ticker, company_name, filed_date, window_days)
    articles.extend(na_articles)

    # Deduplicate by URL
    seen_urls: set[str] = set()
    unique: list[dict] = []
    for a in articles:
        url = a.get("url") or a.get("link") or ""
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(a)

    count = len(unique)
    score = _normalize_score(count)

    log.info("Coverage for %s (%s): %d articles → score %.2f", ticker, filed_date, count, score)

    result = {"score": score, "count": count, "articles": [
        {"title": a.get("title", ""), "url": a.get("url") or a.get("link", "")}
        for a in unique[:20]
    ]}
    if use_cache:
        _save_cache(ticker, filed_date, result)

    return score, count


def get_coverage_scores_batch(
    filings: list[dict],
    use_cache: bool = True,
    rate_limit_sec: float = 1.0,
) -> dict[str, tuple[float, int]]:
    """
    Fetch coverage for a list of {ticker, name, filed} dicts.
    Returns {accession: (score, count)}.
    Respects rate limiting between requests.
    """
    results: dict[str, tuple[float, int]] = {}
    for f in filings:
        ticker   = f.get("ticker", "")
        name     = f.get("name", ticker)
        filed    = f.get("filed", "")
        accession = f.get("accession", f"{ticker}:{filed}")
        try:
            score, count = get_coverage_score(ticker, name, filed, use_cache=use_cache)
            results[accession] = (score, count)
        except Exception as e:
            log.warning("Coverage fetch failed for %s %s: %s", ticker, filed, e)
            results[accession] = (0.5, 0)  # neutral fallback
        time.sleep(rate_limit_sec)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    score, count = get_coverage_score("AAPL", "Apple Inc.", "2024-11-01")
    print(f"AAPL 2024-11-01: {count} articles, coverage={score:.3f}")
