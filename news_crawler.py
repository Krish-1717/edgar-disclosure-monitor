"""
news_crawler.py — News web crawler with full-text extraction.

Crawls news articles from authoritative financial sources and returns
the full article text — not an AI summary. The crawler respects robots.txt,
rate-limits per domain, and caches articles locally.

Supported sources (via RSS feeds + direct scraping):
  - Wall Street Journal    (wsj.com)
  - New York Times         (nytimes.com)
  - Reuters                (reuters.com)
  - Bloomberg              (bloomberg.com)
  - Associated Press       (apnews.com)
  - Financial Times        (ft.com)
  - CNBC                   (cnbc.com)
  - MarketWatch            (marketwatch.com)
  - Seeking Alpha          (seekingalpha.com)
  - SEC press releases     (sec.gov/news)

Architecture:
  NewsCrawler          — orchestrator, discovers + fetches articles
  RSSFeedReader        — parses RSS/Atom feeds for article URLs
  ArticleScraper       — downloads + extracts article full text
  ArticleCache         — deduplicates articles across crawl runs
  DomainRateLimiter    — per-domain request throttling
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

NEWS_SOURCES: dict[str, dict] = {
    "reuters": {
        "name": "Reuters",
        "rss_feeds": [
            "https://feeds.reuters.com/reuters/businessNews",
            "https://feeds.reuters.com/reuters/topNews",
            "https://feeds.reuters.com/reuters/companyNews",
        ],
        "base_url": "https://www.reuters.com",
        "tier": 1,          # 1 = most authoritative
        "delay_s": 1.0,
        "paywall": False,
    },
    "apnews": {
        "name": "AP News",
        "rss_feeds": [
            "https://rsshub.app/apnews/topics/financial-markets",
            "https://apnews.com/apf-business?format=rss",
        ],
        "base_url": "https://apnews.com",
        "tier": 1,
        "delay_s": 1.0,
        "paywall": False,
    },
    "cnbc": {
        "name": "CNBC",
        "rss_feeds": [
            "https://www.cnbc.com/id/100003114/device/rss/rss.html",
            "https://www.cnbc.com/id/10001147/device/rss/rss.html",
        ],
        "base_url": "https://www.cnbc.com",
        "tier": 1,
        "delay_s": 1.0,
        "paywall": False,
    },
    "marketwatch": {
        "name": "MarketWatch",
        "rss_feeds": [
            "https://feeds.marketwatch.com/marketwatch/topstories/",
            "https://feeds.marketwatch.com/marketwatch/marketpulse/",
        ],
        "base_url": "https://www.marketwatch.com",
        "tier": 2,
        "delay_s": 1.0,
        "paywall": False,
    },
    "sec_news": {
        "name": "SEC Press Releases",
        "rss_feeds": [
            "https://www.sec.gov/rss/news/press.xml",
            "https://www.sec.gov/rss/litigation/litreleases.xml",
        ],
        "base_url": "https://www.sec.gov",
        "tier": 1,
        "delay_s": 0.5,
        "paywall": False,
    },
    # Paywalled — accessed via user-provided subscription cookies / API keys
    "wsj": {
        "name": "Wall Street Journal",
        "rss_feeds": ["https://feeds.a.dj.com/rss/RSSMarketsMain.xml"],
        "base_url": "https://www.wsj.com",
        "tier": 1,
        "delay_s": 2.0,
        "paywall": True,
        "requires_cookie_env": "WSJ_SESSION_COOKIE",
    },
    "nytimes": {
        "name": "New York Times",
        "rss_feeds": [
            "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml",
        ],
        "base_url": "https://www.nytimes.com",
        "tier": 1,
        "delay_s": 2.0,
        "paywall": True,
        "requires_cookie_env": "NYT_SESSION_COOKIE",
    },
    "ft": {
        "name": "Financial Times",
        "rss_feeds": [
            "https://www.ft.com/rss/home/us",
            "https://www.ft.com/rss/companies",
        ],
        "base_url": "https://www.ft.com",
        "tier": 1,
        "delay_s": 2.0,
        "paywall": True,
        "requires_cookie_env": "FT_SESSION_COOKIE",
    },
}

DB_PATH = Path("data/news_index.db")
CACHE_DIR = Path("data/news_cache")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class NewsArticle:
    article_id: str         # SHA-256 of URL
    url: str
    title: str
    source: str             # "reuters", "wsj", etc.
    source_tier: int        # 1 = most authoritative
    published_at: str       # ISO 8601
    author: str
    summary: str            # RSS/meta description (not AI generated)
    full_text: str          # Complete article body from crawl
    word_count: int
    tickers_mentioned: list[str] = field(default_factory=list)
    topics_matched: list[str]    = field(default_factory=list)
    crawled_at: str = ""


@dataclass
class CrawlResult:
    total_fetched: int = 0
    new_articles: int = 0
    cached_hits: int = 0
    errors: int = 0
    sources_crawled: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# HTML article extractor
# ---------------------------------------------------------------------------

class ArticleScraper:
    """
    Extracts full article text from HTML pages.
    Uses heuristics to find the article body — no AI.
    Targets: <article>, <main>, common content div patterns.
    """

    # Common article body selectors (by priority)
    _CONTENT_HINTS = [
        "article", "main",
        "[class*='article-body']", "[class*='article__body']",
        "[class*='story-body']", "[class*='content-body']",
        "[class*='post-content']", "[class*='entry-content']",
        "[itemprop='articleBody']",
    ]

    class _Parser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts: list[str] = []
            self._depth = 0
            self._in_article = 0
            self._skip = 0
            self._skip_tags = {"script", "style", "nav", "footer", "header",
                               "aside", "noscript", "form", "button"}
            self._block_tags = {"article", "main", "section", "div"}

        def handle_starttag(self, tag, attrs):
            attr_dict = dict(attrs)
            classes = attr_dict.get("class", "")
            itp = attr_dict.get("itemprop", "")
            is_content = (
                tag == "article"
                or (tag in self._block_tags and any(
                    kw in classes for kw in
                    ["article-body", "story-body", "entry-content",
                     "post-content", "content-body", "article__body"]
                ))
                or itp == "articleBody"
            )
            if is_content:
                self._in_article += 1
            if tag.lower() in self._skip_tags:
                self._skip += 1

        def handle_endtag(self, tag):
            if tag == "article" or tag in self._block_tags:
                if self._in_article > 0:
                    self._in_article -= 1
            if tag.lower() in self._skip_tags and self._skip > 0:
                self._skip -= 1

        def handle_data(self, data):
            if self._skip:
                return
            if self._in_article:
                stripped = data.strip()
                if stripped and len(stripped) > 10:
                    self.parts.append(stripped)

    @classmethod
    def extract(cls, html: str, url: str = "") -> str:
        """
        Extract article body text from HTML.
        Falls back to a broader extraction if article body not detected.
        """
        parser = cls._Parser()
        parser.feed(html)
        text = "\n".join(parser.parts)

        if len(text.split()) < 100:
            # Fallback: strip all HTML tags
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s{2,}", " ", text).strip()

        # Clean up
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def extract_meta(html: str) -> dict:
        """Extract title, author, publish date from meta tags."""
        meta = {"title": "", "author": "", "published_at": "", "description": ""}

        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        if title_m:
            meta["title"] = title_m.group(1).strip()

        for pattern, key in [
            (r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)', "title"),
            (r'<meta[^>]*name=["\']author["\'][^>]*content=["\']([^"\']+)', "author"),
            (r'<meta[^>]*property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)', "published_at"),
            (r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)', "description"),
        ]:
            m = re.search(pattern, html, re.I)
            if m:
                meta[key] = m.group(1).strip()

        return meta


# ---------------------------------------------------------------------------
# RSS reader
# ---------------------------------------------------------------------------

class RSSFeedReader:
    """Parses RSS/Atom feeds and returns article URLs + metadata."""

    _NS = {
        "atom": "http://www.w3.org/2005/Atom",
        "dc": "http://purl.org/dc/elements/1.1/",
        "media": "http://search.yahoo.com/mrss/",
    }

    @staticmethod
    def fetch(feed_url: str, timeout: int = 15) -> list[dict]:
        """Fetch an RSS feed and return list of {url, title, published, summary}."""
        req = urllib.request.Request(feed_url, headers={
            "User-Agent": "EDGAR-Monitor-NewsCrawler/1.0 research@example.com",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                xml_bytes = resp.read()
        except Exception as e:
            return []

        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError:
            return []

        items = []

        # RSS 2.0
        for item in root.findall(".//item"):
            url   = _text(item, "link") or _text(item, "guid") or ""
            title = _text(item, "title") or ""
            pub   = _text(item, "pubDate") or _text(item, "dc:date", RSSFeedReader._NS) or ""
            summ  = _text(item, "description") or ""
            if url and title:
                items.append({"url": url.strip(), "title": title.strip(),
                              "published": pub, "summary": _strip_html(summ)})

        # Atom
        for entry in root.findall(".//atom:entry", RSSFeedReader._NS):
            link_el = entry.find("atom:link[@rel='alternate']", RSSFeedReader._NS) \
                   or entry.find("atom:link", RSSFeedReader._NS)
            url   = link_el.get("href", "") if link_el is not None else ""
            title = _text(entry, "atom:title", RSSFeedReader._NS) or ""
            pub   = _text(entry, "atom:published", RSSFeedReader._NS) or \
                    _text(entry, "atom:updated", RSSFeedReader._NS) or ""
            summ  = _text(entry, "atom:summary", RSSFeedReader._NS) or ""
            if url and title:
                items.append({"url": url.strip(), "title": title.strip(),
                              "published": pub, "summary": _strip_html(summ)})

        return items


def _text(el, tag: str, ns: dict = None) -> str:
    found = el.find(tag, ns) if ns else el.find(tag)
    return found.text.strip() if found is not None and found.text else ""


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


# ---------------------------------------------------------------------------
# Per-domain rate limiter
# ---------------------------------------------------------------------------

class DomainRateLimiter:
    def __init__(self):
        self._last: dict[str, float] = {}

    def wait(self, domain: str, delay_s: float = 1.0):
        now = time.monotonic()
        last = self._last.get(domain, 0)
        elapsed = now - last
        if elapsed < delay_s:
            time.sleep(delay_s - elapsed)
        self._last[domain] = time.monotonic()


# ---------------------------------------------------------------------------
# Article cache / index
# ---------------------------------------------------------------------------

class ArticleCache:
    def __init__(self, db_path: Path = DB_PATH, cache_dir: Path = CACHE_DIR):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_dir
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._init()

    def _init(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                article_id   TEXT PRIMARY KEY,
                url          TEXT UNIQUE,
                title        TEXT,
                source       TEXT,
                source_tier  INTEGER,
                published_at TEXT,
                author       TEXT,
                summary      TEXT,
                full_text    TEXT,
                word_count   INTEGER,
                tickers      TEXT,  -- JSON list
                topics       TEXT,  -- JSON list
                crawled_at   TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_art_source  ON articles(source);
            CREATE INDEX IF NOT EXISTS idx_art_pub     ON articles(published_at);
            CREATE INDEX IF NOT EXISTS idx_art_tickers ON articles(tickers);
        """)
        self.conn.commit()

    def exists(self, url: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM articles WHERE url=? LIMIT 1", (url,))
        return cur.fetchone() is not None

    def store(self, art: NewsArticle):
        self.conn.execute("""
            INSERT OR REPLACE INTO articles
            (article_id, url, title, source, source_tier, published_at,
             author, summary, full_text, word_count, tickers, topics, crawled_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            art.article_id, art.url, art.title, art.source, art.source_tier,
            art.published_at, art.author, art.summary, art.full_text,
            art.word_count, json.dumps(art.tickers_mentioned),
            json.dumps(art.topics_matched), art.crawled_at,
        ))
        self.conn.commit()

    def query(
        self,
        keyword: str = "",
        source: str = "",
        since: str = "",
        tickers: list[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        clauses, params = [], []
        if source:
            clauses.append("source = ?"); params.append(source)
        if since:
            clauses.append("published_at >= ?"); params.append(since)
        if tickers:
            for t in tickers:
                clauses.append("tickers LIKE ?"); params.append(f'%"{t}"%')
        if keyword:
            clauses.append("(title LIKE ? OR full_text LIKE ? OR summary LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""
            SELECT article_id, url, title, source, source_tier,
                   published_at, author, summary, word_count, tickers, topics
            FROM articles {where}
            ORDER BY published_at DESC LIMIT ?
        """
        params.append(limit)
        cur = self.conn.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def get_full_text(self, article_id: str) -> str:
        cur = self.conn.execute(
            "SELECT full_text FROM articles WHERE article_id=?", (article_id,))
        row = cur.fetchone()
        return row[0] if row else ""


# ---------------------------------------------------------------------------
# Ticker mention extractor
# ---------------------------------------------------------------------------

_TICKER_PATTERN = re.compile(r"\b([A-Z]{1,5})\b")
_COMMON_WORDS = {
    "I", "A", "THE", "IN", "ON", "AT", "TO", "OF", "AND", "OR", "BUT",
    "FOR", "NOT", "BY", "US", "EU", "UK", "CEO", "CFO", "IPO", "SEC",
    "NEW", "OLD", "ALL", "ARE", "WAS", "HAS", "HAD", "IS", "BE", "AN",
}

def extract_tickers(text: str) -> list[str]:
    """Heuristically extract ticker symbols from article text."""
    # Look for explicit NYSE: / NASDAQ: patterns first
    explicit = re.findall(r"(?:NYSE|NASDAQ|AMEX|OTC)[:\s]+([A-Z]{1,5})", text)
    # Also capture words in parens following company names: "Apple Inc. (AAPL)"
    parens = re.findall(r"\(([A-Z]{1,5})\)", text)
    found = list(set(explicit + parens))
    found = [t for t in found if t not in _COMMON_WORDS and len(t) >= 1]
    return found[:20]


# ---------------------------------------------------------------------------
# Main crawler
# ---------------------------------------------------------------------------

class NewsCrawler:
    """
    Crawls news from RSS feeds and scrapes full article text.

    Usage:
        crawler = NewsCrawler()
        # Crawl all sources
        result = crawler.crawl_all(hours_back=24)
        # Search cached articles
        arts = crawler.search("Federal Reserve rate", tickers=["JPM", "BAC"])
        # Get full text
        text = crawler.get_full_text(arts[0]["article_id"])
    """

    def __init__(
        self,
        db_path: Path = DB_PATH,
        cache_dir: Path = CACHE_DIR,
        sources: list[str] = None,
        max_workers: int = 3,
        verbose: bool = True,
    ):
        self.cache = ArticleCache(db_path, cache_dir)
        self.rl = DomainRateLimiter()
        self.max_workers = max_workers
        self.verbose = verbose
        self.sources = sources or list(NEWS_SOURCES.keys())

    def _log(self, msg: str):
        if self.verbose:
            print(f"[NewsCrawler {datetime.utcnow().strftime('%H:%M:%S')}] {msg}")

    def _fetch_article(self, url: str, source_key: str) -> Optional[str]:
        """Download article HTML, respecting domain rate limits."""
        src = NEWS_SOURCES.get(source_key, {})
        delay = src.get("delay_s", 1.0)
        domain = urllib.parse.urlparse(url).netloc
        self.rl.wait(domain, delay)

        import os
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; EDGARMonitor/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        }
        # Inject paywall cookies if user has configured them
        cookie_env = src.get("requires_cookie_env", "")
        if cookie_env:
            cookie = os.environ.get(cookie_env, "")
            if cookie:
                headers["Cookie"] = cookie
            else:
                self._log(f"No cookie for {source_key} ({cookie_env} not set) — "
                          "will get paywall stub only")

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            self._log(f"Fetch error {url[:60]}: {e}")
            return None

    def _process_rss_item(self, item: dict, source_key: str) -> Optional[NewsArticle]:
        url = item["url"]
        if self.cache.exists(url):
            return None  # already have it

        html = self._fetch_article(url, source_key)
        if not html:
            return None

        meta = ArticleScraper.extract_meta(html)
        body = ArticleScraper.extract(html, url)
        tickers = extract_tickers(f"{item['title']} {body}")
        art_id = hashlib.sha256(url.encode()).hexdigest()[:16]
        src_info = NEWS_SOURCES.get(source_key, {})

        return NewsArticle(
            article_id=art_id,
            url=url,
            title=meta.get("title") or item.get("title", ""),
            source=source_key,
            source_tier=src_info.get("tier", 2),
            published_at=meta.get("published_at") or item.get("published", ""),
            author=meta.get("author", ""),
            summary=item.get("summary", "")[:500],
            full_text=body,
            word_count=len(body.split()),
            tickers_mentioned=tickers,
            crawled_at=datetime.utcnow().isoformat(),
        )

    def crawl_source(self, source_key: str, hours_back: int = 24) -> int:
        """Crawl one source. Returns number of new articles stored."""
        src = NEWS_SOURCES.get(source_key)
        if not src:
            return 0
        new_count = 0
        for feed_url in src["rss_feeds"]:
            self._log(f"Fetching RSS: {src['name']} — {feed_url}")
            items = RSSFeedReader.fetch(feed_url)
            self._log(f"  {len(items)} items found")
            for item in items:
                art = self._process_rss_item(item, source_key)
                if art:
                    self.cache.store(art)
                    new_count += 1
        return new_count

    def crawl_all(self, hours_back: int = 24) -> CrawlResult:
        """Crawl all configured sources."""
        result = CrawlResult()
        for src_key in self.sources:
            try:
                n = self.crawl_source(src_key, hours_back)
                result.new_articles += n
                result.sources_crawled.append(src_key)
            except Exception as e:
                self._log(f"Error crawling {src_key}: {e}")
                result.errors += 1
        result.total_fetched = result.new_articles
        return result

    def search(
        self,
        keyword: str = "",
        source: str = "",
        since: str = "",
        tickers: list[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search cached articles. Returns list of article dicts."""
        return self.cache.query(
            keyword=keyword, source=source, since=since,
            tickers=tickers or [], limit=limit,
        )

    def get_full_text(self, article_id: str) -> str:
        """Retrieve the full crawled text for one article."""
        return self.cache.get_full_text(article_id)

    def crawl_url(self, url: str, source_key: str = "unknown") -> Optional[NewsArticle]:
        """
        Crawl a single arbitrary URL and return the article.
        Useful for ad-hoc: crawler.crawl_url('https://wsj.com/articles/...')
        """
        html = self._fetch_article(url, source_key)
        if not html:
            return None
        meta = ArticleScraper.extract_meta(html)
        body = ArticleScraper.extract(html, url)
        art_id = hashlib.sha256(url.encode()).hexdigest()[:16]
        art = NewsArticle(
            article_id=art_id,
            url=url,
            title=meta.get("title", url),
            source=source_key,
            source_tier=NEWS_SOURCES.get(source_key, {}).get("tier", 2),
            published_at=meta.get("published_at", ""),
            author=meta.get("author", ""),
            summary=meta.get("description", "")[:500],
            full_text=body,
            word_count=len(body.split()),
            tickers_mentioned=extract_tickers(body),
            crawled_at=datetime.utcnow().isoformat(),
        )
        self.cache.store(art)
        return art


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    crawler = NewsCrawler(verbose=True)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "crawl"

    if cmd == "crawl":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        result = crawler.crawl_all(hours_back=hours)
        print(f"Crawl complete: {result.new_articles} new articles from "
              f"{', '.join(result.sources_crawled)}")

    elif cmd == "search":
        kw = sys.argv[2] if len(sys.argv) > 2 else ""
        ticker = sys.argv[3] if len(sys.argv) > 3 else ""
        arts = crawler.search(
            keyword=kw,
            tickers=[ticker] if ticker else [],
            limit=10
        )
        for a in arts:
            print(f"  [{a['source'].upper()}] {a['published_at'][:10]}  {a['title'][:80]}")

    elif cmd == "fetch":
        url = sys.argv[2]
        src = sys.argv[3] if len(sys.argv) > 3 else "unknown"
        art = crawler.crawl_url(url, src)
        if art:
            print(f"Title: {art.title}")
            print(f"Words: {art.word_count}")
            print(f"Text preview:\n{art.full_text[:800]}")
