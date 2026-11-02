"""
edgar_web_crawler.py â Comprehensive SEC EDGAR web crawler.

Systematically crawls the full EDGAR database to index filings for ALL public
companies. Covers 10-K, 10-Q, 8-K, DEF 14A, S-1, and more. Stores an index
locally so the user can search and retrieve any filing without re-crawling.

Architecture:
  EDGARCrawler          â orchestrates company discovery + filing crawl
  FilingIndexer         â maintains a local SQLite index of crawled filings
  FilingDownloader      â downloads and caches raw filing HTML/text
  FullTextExtractor     â strips HTML â plain text, no AI summarization
  CrawlerRateLimiter    â respects SEC fair-access policy (max 10 req/s)
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, Optional
from html.parser import HTMLParser


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EDGAR_BASE        = "https://www.sec.gov"
EDGAR_COMPANY_API = "https://data.sec.gov/submissions/{cik}.json"
EDGAR_SEARCH_API  = "https://efts.sec.gov/LATEST/search-index?q=%22{query}%22&dateRange=custom&startdt={start}&enddt={end}&forms={forms}"
EDGAR_FULL_IDX    = "https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{qtr}/company.idx"
COMPANY_TICKERS   = "https://www.sec.gov/files/company_tickers.json"

FORM_TYPES = ["10-K", "10-Q", "8-K", "DEF 14A", "S-1", "S-11", "20-F", "6-K", "SC 13G", "4"]

# SEC requests: polite crawl = max 10/second, we use 5 to be safe
CRAWL_DELAY_S = 0.2

DEFAULT_DB = Path("data/edgar_index.db")
DEFAULT_CACHE = Path("data/filing_cache")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CompanyRecord:
    cik: str               # zero-padded 10-digit CIK
    name: str
    ticker: str
    sic: str               # industry code
    sic_description: str
    state: str
    fiscal_year_end: str   # MMDD


@dataclass
class FilingRecord:
    cik: str
    accession: str         # "0001234567-23-000001"
    form_type: str         # "10-K", "10-Q", etc.
    filed_date: str        # "2024-03-15"
    period_of_report: str  # "2023-12-31"
    company_name: str
    ticker: str
    file_url: str          # direct link to primary document
    full_text: str = ""    # populated after download
    crawled_at: str = ""


@dataclass
class CrawlStats:
    companies_indexed: int = 0
    filings_found: int = 0
    filings_downloaded: int = 0
    errors: int = 0
    started_at: str = ""
    completed_at: str = ""
    forms_breakdown: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class CrawlerRateLimiter:
    """Token-bucket rate limiter respecting SEC's 10 req/s policy."""

    def __init__(self, requests_per_second: float = 5.0):
        self._min_interval = 1.0 / requests_per_second
        self._last_call = 0.0

    def wait(self):
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()


# ---------------------------------------------------------------------------
# HTML â plain-text extractor (no AI, raw content only)
# ---------------------------------------------------------------------------

class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip_tags = {"script", "style", "noscript", "head"}
        self._in_skip = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self._skip_tags:
            self._in_skip += 1

    def handle_endtag(self, tag):
        if tag.lower() in self._skip_tags and self._in_skip:
            self._in_skip -= 1

    def handle_data(self, data):
        if not self._in_skip:
            stripped = data.strip()
            if stripped:
                self._parts.append(stripped)

    def get_text(self) -> str:
        return "\n".join(self._parts)


class FullTextExtractor:
    """Extract raw text from SEC filing HTML. No AI. No summarization."""

    @staticmethod
    def from_html(html: str) -> str:
        stripper = _HTMLStripper()
        stripper.feed(html)
        text = stripper.get_text()
        # Collapse excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()

    @staticmethod
    def extract_sections(text: str) -> dict[str, str]:
        """
        Extract named sections from 10-K / 10-Q plain text.
        Returns dict: {section_name: section_text}
        Sections: Item 1, Item 1A, Item 2, Item 7, Item 7A, Item 8, etc.
        """
        section_pattern = re.compile(
            r"(?:ITEM|Item)\s+(\d+[A-Z]?)\s*[.\-â]?\s*([^\n]{0,80})\n",
            re.MULTILINE
        )
        sections: dict[str, str] = {}
        matches = list(section_pattern.finditer(text))
        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            key = f"Item {m.group(1)} â {m.group(2).strip()}"
            sections[key] = text[start:end].strip()[:10_000]  # cap at 10KB per section
        return sections


# ---------------------------------------------------------------------------
# Local SQLite index
# ---------------------------------------------------------------------------

class FilingIndexer:
    """Maintains a local index of all crawled EDGAR filings."""

    def __init__(self, db_path: Path = DEFAULT_DB):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS companies (
                cik TEXT PRIMARY KEY,
                name TEXT,
                ticker TEXT,
                sic TEXT,
                sic_description TEXT,
                state TEXT,
                fiscal_year_end TEXT,
                indexed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS filings (
                accession TEXT PRIMARY KEY,
                cik TEXT,
                form_type TEXT,
                filed_date TEXT,
                period_of_report TEXT,
                company_name TEXT,
                ticker TEXT,
                file_url TEXT,
                has_full_text INTEGER DEFAULT 0,
                crawled_at TEXT,
                FOREIGN KEY(cik) REFERENCES companies(cik)
            );
            CREATE INDEX IF NOT EXISTS idx_filings_cik       ON filings(cik);
            CREATE INDEX IF NOT EXISTS idx_filings_form      ON filings(form_type);
            CREATE INDEX IF NOT EXISTS idx_filings_date      ON filings(filed_date);
            CREATE INDEX IF NOT EXISTS idx_filings_ticker    ON filings(ticker);
            CREATE TABLE IF NOT EXISTS full_text (
                accession TEXT PRIMARY KEY,
                raw_text  TEXT,
                sections  TEXT,  -- JSON dict
                word_count INTEGER
            );
        """)
        self.conn.commit()

    def upsert_company(self, c: CompanyRecord):
        self.conn.execute("""
            INSERT OR REPLACE INTO companies
            (cik, name, ticker, sic, sic_description, state, fiscal_year_end, indexed_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (c.cik, c.name, c.ticker, c.sic, c.sic_description,
              c.state, c.fiscal_year_end, datetime.utcnow().isoformat()))
        self.conn.commit()

    def upsert_filing(self, f: FilingRecord):
        self.conn.execute("""
            INSERT OR REPLACE INTO filings
            (accession, cik, form_type, filed_date, period_of_report,
             company_name, ticker, file_url, crawled_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (f.accession, f.cik, f.form_type, f.filed_date, f.period_of_report,
              f.company_name, f.ticker, f.file_url,
              datetime.utcnow().isoformat()))
        self.conn.commit()

    def store_full_text(self, accession: str, text: str, sections: dict):
        self.conn.execute("""
            INSERT OR REPLACE INTO full_text (accession, raw_text, sections, word_count)
            VALUES (?,?,?,?)
        """, (accession, text, json.dumps(sections), len(text.split())))
        self.conn.execute(
            "UPDATE filings SET has_full_text=1 WHERE accession=?", (accession,))
        self.conn.commit()

    def search_filings(
        self,
        ticker: str = "",
        form_type: str = "",
        start_date: str = "",
        end_date: str = "",
        keyword: str = "",
        limit: int = 50,
    ) -> list[dict]:
        """Full-text and metadata search across the index."""
        clauses, params = [], []
        if ticker:
            clauses.append("f.ticker = ?")
            params.append(ticker.upper())
        if form_type:
            clauses.append("f.form_type = ?")
            params.append(form_type)
        if start_date:
            clauses.append("f.filed_date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("f.filed_date <= ?")
            params.append(end_date)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        if keyword:
            # Full-text search in raw_text
            sql = f"""
                SELECT f.*, ft.word_count
                FROM filings f
                LEFT JOIN full_text ft ON f.accession = ft.accession
                {where}
                {'AND' if where else 'WHERE'} ft.raw_text LIKE ?
                ORDER BY f.filed_date DESC LIMIT ?
            """
            params.extend([f"%{keyword}%", limit])
        else:
            sql = f"""
                SELECT f.*, ft.word_count
                FROM filings f
                LEFT JOIN full_text ft ON f.accession = ft.accession
                {where}
                ORDER BY f.filed_date DESC LIMIT ?
            """
            params.append(limit)

        cur = self.conn.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def get_company_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]

    def get_filing_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM filings").fetchone()[0]

    def close(self):
        self.conn.close()


# ---------------------------------------------------------------------------
# Downloader
# ---------------------------------------------------------------------------

class FilingDownloader:
    """Downloads SEC filing documents with caching and rate limiting."""

    def __init__(
        self,
        cache_dir: Path = DEFAULT_CACHE,
        rate_limiter: Optional[CrawlerRateLimiter] = None,
    ):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.rl = rate_limiter or CrawlerRateLimiter()

    def _cache_path(self, accession: str) -> Path:
        safe = accession.replace("/", "_").replace("-", "_")
        return self.cache_dir / f"{safe}.html"

    def get(self, url: str, accession: str = "") -> str:
        """Fetch URL, using disk cache when available."""
        if accession:
            cp = self._cache_path(accession)
            if cp.exists():
                return cp.read_text(encoding="utf-8", errors="replace")

        self.rl.wait()
        req = urllib.request.Request(url, headers={
            "User-Agent": "EDGAR-Disclosure-Monitor research@example.com",
            "Accept": "text/html,application/xhtml+xml,*/*",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            raise RuntimeError(f"Download failed: {url} â {e}") from e

        if accession:
            cp = self._cache_path(accession)
            cp.write_text(html, encoding="utf-8")
        return html

    def get_json(self, url: str) -> dict:
        """Fetch a JSON endpoint."""
        self.rl.wait()
        req = urllib.request.Request(url, headers={
            "User-Agent": "EDGAR-Disclosure-Monitor research@example.com",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Main crawler
# ---------------------------------------------------------------------------

class EDGARCrawler:
    """
    Orchestrates full crawl of SEC EDGAR.

    Usage:
        crawler = EDGARCrawler()
        # Index all companies (~12,000 public companies)
        crawler.index_all_companies()
        # Crawl filings for a specific ticker
        crawler.crawl_ticker("NVDA", forms=["10-K", "10-Q"])
        # Crawl everything (long running â use max_companies to limit)
        crawler.crawl_all(forms=["10-K"], years_back=3, max_companies=500)
        # Search
        results = crawler.search("AI risk factors", ticker="MSFT")
    """

    def __init__(
        self,
        db_path: Path = DEFAULT_DB,
        cache_dir: Path = DEFAULT_CACHE,
        max_workers: int = 4,
        verbose: bool = True,
    ):
        self.indexer = FilingIndexer(db_path)
        self.downloader = FilingDownloader(cache_dir)
        self.extractor = FullTextExtractor()
        self.max_workers = max_workers
        self.verbose = verbose
        self._companies: dict[str, CompanyRecord] = {}  # ticker â record

    def _log(self, msg: str):
        if self.verbose:
            print(f"[EDGARCrawler {datetime.utcnow().strftime('%H:%M:%S')}] {msg}")

    # ------------------------------------------------------------------
    # Company discovery
    # ------------------------------------------------------------------

    def index_all_companies(self) -> int:
        """
        Downloads the master company ticker list from EDGAR (~12,000 companies).
        Returns number of companies indexed.
        """
        self._log("Fetching master company list from EDGARâ¦")
        data = self.downloader.get_json(COMPANY_TICKERS)
        count = 0
        for entry in data.values():
            cik = str(entry.get("cik_str", "")).zfill(10)
            ticker = str(entry.get("ticker", "")).upper()
            name = str(entry.get("title", ""))
            rec = CompanyRecord(
                cik=cik, name=name, ticker=ticker,
                sic="", sic_description="", state="", fiscal_year_end=""
            )
            self._companies[ticker] = rec
            self.indexer.upsert_company(rec)
            count += 1
        self._log(f"Indexed {count} companies.")
        return count

    def get_company_submissions(self, cik: str) -> dict:
        """Fetch full submission history for one company."""
        url = EDGAR_COMPANY_API.format(cik=cik.zfill(10))
        return self.downloader.get_json(url)

    # ------------------------------------------------------------------
    # Filing crawl
    # ------------------------------------------------------------------

    def crawl_ticker(
        self,
        ticker: str,
        forms: list[str] = None,
        years_back: int = 5,
        download_full_text: bool = True,
    ) -> list[FilingRecord]:
        """Crawl all filings for one ticker."""
        forms = forms or ["10-K", "10-Q", "8-K"]
        if not self._companies:
            self.index_all_companies()

        rec = self._companies.get(ticker.upper())
        if not rec:
            self._log(f"Ticker {ticker} not found in company index.")
            return []

        self._log(f"Crawling {ticker} ({rec.cik})â¦")
        try:
            subs = self.get_company_submissions(rec.cik)
        except Exception as e:
            self._log(f"Error fetching submissions for {ticker}: {e}")
            return []

        filings = self._parse_submissions(subs, rec, forms, years_back)
        self._log(f"Found {len(filings)} filings for {ticker}.")

        if download_full_text:
            for f in filings:
                self._download_full_text(f)

        return filings

    def _parse_submissions(
        self,
        subs: dict,
        company: CompanyRecord,
        forms: list[str],
        years_back: int,
    ) -> list[FilingRecord]:
        """Parse EDGAR submissions JSON into FilingRecord objects."""
        cutoff = (datetime.utcnow() - timedelta(days=365 * years_back)).strftime("%Y-%m-%d")
        recent = subs.get("filings", {}).get("recent", {})

        accessions  = recent.get("accessionNumber", [])
        form_types  = recent.get("form", [])
        filed_dates = recent.get("filingDate", [])
        periods     = recent.get("reportDate", [])
        primary_docs= recent.get("primaryDocument", [])

        results = []
        for i, acc in enumerate(accessions):
            ft = form_types[i] if i < len(form_types) else ""
            fd = filed_dates[i] if i < len(filed_dates) else ""
            if ft not in forms:
                continue
            if fd and fd < cutoff:
                continue

            acc_clean = acc.replace("-", "")
            doc = primary_docs[i] if i < len(primary_docs) else ""
            file_url = (
                f"{EDGAR_BASE}/Archives/edgar/data/{company.cik.lstrip('0')}/"
                f"{acc_clean}/{doc}"
            ) if doc else ""

            fr = FilingRecord(
                cik=company.cik,
                accession=acc,
                form_type=ft,
                filed_date=fd,
                period_of_report=periods[i] if i < len(periods) else "",
                company_name=company.name,
                ticker=company.ticker,
                file_url=file_url,
            )
            self.indexer.upsert_filing(fr)
            results.append(fr)
        return results

    def _download_full_text(self, filing: FilingRecord):
        """Download and index full text for one filing."""
        if not filing.file_url:
            return
        try:
            html = self.downloader.get(filing.file_url, accession=filing.accession)
            text = FullTextExtractor.from_html(html)
            sections = FullTextExtractor.extract_sections(text)
            self.indexer.store_full_text(filing.accession, text, sections)
        except Exception as e:
            self._log(f"Full-text download failed for {filing.accession}: {e}")

    def crawl_all(
        self,
        forms: list[str] = None,
        years_back: int = 3,
        max_companies: int = 0,
        download_full_text: bool = False,
    ) -> CrawlStats:
        """
        Crawl filings for ALL indexed companies.

        Args:
            forms: Filing types to crawl (default 10-K, 10-Q, 8-K).
            years_back: How far back to go.
            max_companies: Cap crawl (0 = unlimited â full crawl takes hours).
            download_full_text: Whether to also download full filing text.

        Returns:
            CrawlStats with summary counts.
        """
        forms = forms or ["10-K", "10-Q", "8-K"]
        if not self._companies:
            self.index_all_companies()

        stats = CrawlStats(started_at=datetime.utcnow().isoformat())
        companies = list(self._companies.values())
        if max_companies:
            companies = companies[:max_companies]

        self._log(f"Starting full crawl: {len(companies)} companies, forms={forms}")

        def crawl_one(company: CompanyRecord):
            try:
                subs = self.get_company_submissions(company.cik)
                filings = self._parse_submissions(subs, company, forms, years_back)
                return len(filings), 0
            except Exception:
                return 0, 1

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(crawl_one, c): c for c in companies}
            for i, fut in enumerate(as_completed(futures)):
                found, err = fut.result()
                stats.filings_found += found
                stats.errors += err
                stats.companies_indexed += 1
                if i % 100 == 0:
                    self._log(f"Progress: {i}/{len(companies)} companies, "
                              f"{stats.filings_found} filings indexed")

        stats.completed_at = datetime.utcnow().isoformat()
        self._log(f"Crawl complete: {stats.companies_indexed} companies, "
                  f"{stats.filings_found} filings, {stats.errors} errors.")
        return stats

    # ------------------------------------------------------------------
    # Search interface
    # ------------------------------------------------------------------

    def search(
        self,
        keyword: str = "",
        ticker: str = "",
        form_type: str = "",
        start_date: str = "",
        end_date: str = "",
        limit: int = 20,
    ) -> list[dict]:
        """
        Search the local index.

        Returns a list of filing dicts with metadata.
        Users can then call get_full_text(accession) to read the full document.
        """
        return self.indexer.search_filings(
            ticker=ticker,
            form_type=form_type,
            start_date=start_date,
            end_date=end_date,
            keyword=keyword,
            limit=limit,
        )

    def get_full_text(self, accession: str) -> dict:
        """
        Retrieve the full text and extracted sections for one filing.
        Returns: {raw_text, sections, word_count} or {} if not downloaded.
        """
        cur = self.indexer.conn.execute(
            "SELECT raw_text, sections, word_count FROM full_text WHERE accession=?",
            (accession,)
        )
        row = cur.fetchone()
        if not row:
            return {}
        return {
            "raw_text": row[0],
            "sections": json.loads(row[1]) if row[1] else {},
            "word_count": row[2],
        }

    def get_stats(self) -> dict:
        return {
            "companies_indexed": self.indexer.get_company_count(),
            "filings_indexed": self.indexer.get_filing_count(),
            "db_path": str(DEFAULT_DB),
            "cache_dir": str(DEFAULT_CACHE),
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    crawler = EDGARCrawler(verbose=True)

    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"

    if cmd == "index":
        n = crawler.index_all_companies()
        print(f"Indexed {n} companies.")

    elif cmd == "crawl" and len(sys.argv) > 2:
        ticker = sys.argv[2]
        forms = sys.argv[3].split(",") if len(sys.argv) > 3 else ["10-K", "10-Q"]
        filings = crawler.crawl_ticker(ticker, forms=forms, download_full_text=True)
        print(f"Crawled {len(filings)} filings for&ôicker}:")
        for f in filings[:5]:
            print(f"  {f.form_type}  {f.filed_date}  {f.accession}")

    elif cmd == "search":
        keyword = sys.argv[2] if len(sys.argv) > 2 else ""
        ticker  = sys.argv[3] if len(sys.argv) > 3 else ""
        results = crawler.search(keyword=keyword, ticker=ticker, limit=10)
        print(f"Found {len(results)} results:")
        for r in results:
            print(f"  [{r['form_type']}] {r['ticker']} {r['filed_date']} â {r['company_name']}")

    elif cmd == "full-crawl":
        max_c = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        stats = crawler.crawl_all(max_companies=max_c)
        print(f"Stats: {stats}")

    else:
        print(json.dumps(crawler.get_stats(), indent=2))
