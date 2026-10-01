"""
edgar_client.py — EDGAR API Client
Rate-limited, cached, retry-backed client for SEC EDGAR.

SEC requirements:
- User-Agent must include name and email (enforced, returns 403 otherwise)
- Rate limit: ≤10 req/sec; we target 8 req/sec (125ms between calls)
"""
from __future__ import annotations
import time
import json
import hashlib
import pathlib
import logging
import requests
from functools import lru_cache

log = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
BASE_URL      = "https://data.sec.gov"
ARCHIVES_URL  = "https://www.sec.gov/Archives/edgar/data"
TICKERS_URL   = "https://www.sec.gov/files/company_tickers.json"
MIN_INTERVAL  = 0.125        # 8 req/sec
CACHE_DIR     = pathlib.Path("data/cache")
MAX_RETRIES   = 3
BACKOFF_BASE  = 2.0          # seconds


class EdgarClient:
    """Thread-safe EDGAR client with rate limiting and local disk caching."""

    def __init__(self, user_agent: str, cache_dir: pathlib.Path = CACHE_DIR):
        """
        Parameters
        ----------
        user_agent : str
            Must match: "FirstName LastName email@domain.com"
            Example: "Krish Patel patelkrish1717@gmail.com"
        """
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        })
        self._last_call = 0.0
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ── Low-level request ──────────────────────────────────────────────────────

    def _get(self, url: str, use_cache: bool = True) -> bytes:
        """Rate-limited GET with caching and exponential backoff."""
        cache_key = hashlib.md5(url.encode()).hexdigest()
        cache_path = self.cache_dir / f"{cache_key}.cache"

        if use_cache and cache_path.exists():
            log.debug("cache hit: %s", url)
            return cache_path.read_bytes()

        # Rate limiting
        elapsed = time.monotonic() - self._last_call
        if elapsed < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - elapsed)

        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.get(url, timeout=30)
                self._last_call = time.monotonic()
                resp.raise_for_status()
                data = resp.content
                if use_cache:
                    cache_path.write_bytes(data)
                return data
            except requests.HTTPError as e:
                if resp.status_code == 429:
                    wait = BACKOFF_BASE ** (attempt + 1)
                    log.warning("Rate limited. Waiting %.1fs", wait)
                    time.sleep(wait)
                elif resp.status_code == 403:
                    raise RuntimeError(
                        "403 Forbidden — check your User-Agent header. "
                        "SEC requires: 'Name email@domain.com'"
                    ) from e
                else:
                    raise
            except requests.RequestException as e:
                if attempt == MAX_RETRIES - 1:
                    raise
                wait = BACKOFF_BASE ** attempt
                log.warning("Request failed (%s). Retrying in %.1fs", e, wait)
                time.sleep(wait)

    def _get_json(self, url: str, use_cache: bool = True) -> dict:
        return json.loads(self._get(url, use_cache))

    # ── Company lookup ─────────────────────────────────────────────────────────

    def get_ticker_cik_map(self) -> dict[str, str]:
        """Return {ticker: zero-padded CIK (10 digits)}."""
        raw = self._get_json(TICKERS_URL)
        return {
            v["ticker"]: str(v["cik_str"]).zfill(10)
            for v in raw.values()
        }

    @lru_cache(maxsize=512)
    def ticker_to_cik(self, ticker: str) -> str:
        """Resolve ticker → 10-digit CIK string."""
        mapping = self.get_ticker_cik_map()
        ticker_up = ticker.upper()
        if ticker_up not in mapping:
            raise ValueError(f"Ticker {ticker!r} not found in EDGAR")
        return mapping[ticker_up]

    # ── Filing history ─────────────────────────────────────────────────────────

    def get_submissions(self, cik: str) -> dict:
        """Return EDGAR submissions JSON for a CIK (company)."""
        url = f"{BASE_URL}/submissions/CIK{cik}.json"
        return self._get_json(url)

    def get_filings_metadata(
        self, ticker: str, form_types: tuple[str, ...] = ("10-K", "10-Q"),
        since_year: int = 2019,
    ) -> list[dict]:
        """
        Return list of filing dicts for the given ticker/form types.
        Each dict: {ticker, cik, form, filed, period, accession, doc_url}
        """
        cik = self.ticker_to_cik(ticker)
        subs = self.get_submissions(cik)
        filings = subs.get("filings", {}).get("recent", {})

        keys = ["accessionNumber", "filingDate", "reportDate", "form", "primaryDocument"]
        cols = {k: filings.get(k, []) for k in keys}
        n = len(cols["form"])

        results = []
        for i in range(n):
            form   = cols["form"][i]
            filed  = cols["filingDate"][i]
            if form not in form_types:
                continue
            try:
                year = int(filed[:4])
            except (ValueError, IndexError):
                continue
            if year < since_year:
                continue

            accession = cols["accessionNumber"][i].replace("-", "")
            primary   = cols["primaryDocument"][i]
            doc_url   = f"{ARCHIVES_URL}/{cik}/{accession}/{primary}"

            results.append({
                "ticker":    ticker.upper(),
                "cik":       cik,
                "form":      form,
                "filed":     filed,
                "period":    cols["reportDate"][i],
                "accession": cols["accessionNumber"][i],
                "doc_url":   doc_url,
            })

        results.sort(key=lambda x: x["filed"], reverse=True)
        return results

    # ── Document fetch ─────────────────────────────────────────────────────────

    def fetch_document_html(self, doc_url: str) -> str:
        """Fetch and return the raw HTML of a filing document."""
        raw = self._get(doc_url)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1")

    def fetch_document_text(self, doc_url: str) -> str:
        """Fetch and return plain text (HTML stripped) of a filing document."""
        from section_segmenter import html_to_clean_text
        html = self.fetch_document_html(doc_url)
        return html_to_clean_text(html)
