"""
client.py — EDGAR HTTP client.

Day 1: Handles all communication with the SEC EDGAR APIs.
Key properties:
  - Descriptive User-Agent with contact email (required by SEC)
  - Rate limiter: max 8 requests/second (SEC allows 10, we stay below)
  - Exponential backoff retry on 429 and 5xx responses
  - Local disk cache — re-runs cost zero network calls

Usage:
    from edgar.client import EdgarClient
    client = EdgarClient()
    tickers = client.get_company_tickers()
    submissions = client.get_submissions("0000320193")  # Apple CIK
"""

import os
import json
import time
import hashlib
import logging
from pathlib import Path
from typing import Optional, Any
from functools import wraps

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────

EDGAR_BASE        = "https://data.sec.gov"
EDGAR_ARCHIVES    = "https://www.sec.gov/Archives/edgar/data"
EDGAR_FILES_BASE  = "https://www.sec.gov/files"
TICKERS_URL       = "https://www.sec.gov/files/company_tickers.json"

CACHE_DIR         = Path(__file__).parent.parent / ".cache" / "edgar"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# SEC requires a descriptive User-Agent with a contact email.
# Requests without one are blocked. This is the most common Day 1 trap.
USER_AGENT        = "edgar-disclosure-monitor research tool patelkrish1717@gmail.com"

RATE_LIMIT_RPS    = 8        # requests per second (SEC allows 10; stay below)
REQUEST_TIMEOUT   = 30       # seconds


# ── Rate limiter ───────────────────────────────────────────────────────────────

class RateLimiter:
    """Token-bucket rate limiter."""

    def __init__(self, rps: float = RATE_LIMIT_RPS):
        self.min_interval = 1.0 / rps
        self._last_call    = 0.0

    def wait(self):
        now     = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.monotonic()


# ── Cache ─────────────────────────────────────────────────────────────────────

def _cache_path(url: str) -> Path:
    key = hashlib.sha256(url.encode()).hexdigest()
    return CACHE_DIR / f"{key}.json"


def _load_cache(url: str) -> Optional[Any]:
    p = _cache_path(url)
    if p.exists():
        try:
            with p.open() as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _save_cache(url: str, data: Any) -> None:
    p = _cache_path(url)
    try:
        with p.open("w") as f:
            json.dump(data, f)
    except OSError as e:
        logger.warning("Cache write failed for %s: %s", url, e)


# ── EDGAR client ──────────────────────────────────────────────────────────────

class EdgarClient:
    """
    SEC EDGAR HTTP client with rate limiting, retry, and local caching.

    All JSON responses are cached to .cache/edgar/ so re-runs are free.
    Raw HTML document fetches are NOT cached here — see fetch_documents.py.
    """

    def __init__(self, cache: bool = True):
        self.cache   = cache
        self._rl     = RateLimiter()
        self._session = self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "User-Agent":      USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
            "Host":            "data.sec.gov",
        })
        # Retry on transient server errors; NOT on 429 (we handle that manually)
        retry = Retry(
            total=5,
            backoff_factor=1.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _get(self, url: str, host_override: Optional[str] = None) -> Any:
        """
        Fetch JSON from url with caching, rate limiting, and 429 backoff.
        host_override: updates the Host header for www.sec.gov endpoints.
        """
        if self.cache:
            cached = _load_cache(url)
            if cached is not None:
                logger.debug("Cache hit: %s", url)
                return cached

        headers = {}
        if host_override:
            headers["Host"] = host_override

        for attempt in range(6):
            self._rl.wait()
            try:
                resp = self._session.get(
                    url,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                )
                if resp.status_code == 429:
                    wait = 2 ** attempt
                    logger.warning("429 rate-limited by SEC. Waiting %ss (attempt %d)", wait, attempt + 1)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                if self.cache:
                    _save_cache(url, data)
                return data

            except requests.exceptions.JSONDecodeError as e:
                logger.error("JSON decode error for %s: %s", url, e)
                raise
            except requests.exceptions.RequestException as e:
                if attempt == 5:
                    raise
                wait = 2 ** attempt
                logger.warning("Request error (%s). Retrying in %ss...", e, wait)
                time.sleep(wait)

    def _get_text(self, url: str) -> str:
        """Fetch raw text (HTML) content — not cached here."""
        for attempt in range(4):
            self._rl.wait()
            resp = self._session.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp.text
        raise RuntimeError(f"Failed to fetch {url} after retries")

    # ── Public API ────────────────────────────────────────────────────────────

    def get_company_tickers(self) -> dict:
        """
        Fetch the SEC's ticker→CIK map.

        Returns a dict: {str_index: {cik_str, ticker, title}, ...}
        """
        return self._get(TICKERS_URL, host_override="www.sec.gov")

    def get_submissions(self, cik: str) -> dict:
        """
        Fetch filing history for a CIK.

        cik: 10-digit zero-padded string, e.g. "0000320193"

        Returns the full submissions JSON from data.sec.gov.
        """
        padded = cik.zfill(10)
        url = f"{EDGAR_BASE}/submissions/CIK{padded}.json"
        return self._get(url)

    def get_filing_index(self, cik: str, accession: str) -> dict:
        """
        Fetch the filing index (list of documents) for a specific accession.

        accession: with or without dashes, e.g. "0001234567-23-000001"
        """
        acc_nodash = accession.replace("-", "")
        padded     = cik.zfill(10).lstrip("0") or "0"
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{padded}/"
            f"{acc_nodash}/{acc_nodash}-index.json"
        )
        return self._get(url, host_override="www.sec.gov")

    def get_company_facts(self, cik: str) -> dict:
        """Fetch structured financial facts (XBRL) for a company."""
        padded = cik.zfill(10)
        url    = f"{EDGAR_BASE}/api/xbrl/companyfacts/CIK{padded}.json"
        return self._get(url)

    def get_html(self, url: str) -> str:
        """Fetch raw HTML of a filing document."""
        # Switch Host header based on URL
        host = "www.sec.gov" if "www.sec.gov" in url else "data.sec.gov"
        old_host = self._session.headers.get("Host")
        self._session.headers["Host"] = host
        text = self._get_text(url)
        self._session.headers["Host"] = old_host or "data.sec.gov"
        return text

    def ticker_to_cik(self, ticker: str) -> Optional[str]:
        """
        Resolve a ticker symbol to a 10-digit padded CIK string.
        Returns None if the ticker is not found.
        """
        data = self.get_company_tickers()
        ticker_upper = ticker.upper()
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker_upper:
                return str(entry["cik_str"]).zfill(10)
        return None


# ── Quick smoke test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    client = EdgarClient()

    print("Fetching company tickers ...")
    tickers = client.get_company_tickers()
    print(f"  Got {len(tickers):,} tickers.")

    test_ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    cik = client.ticker_to_cik(test_ticker)
    print(f"  {test_ticker} → CIK {cik}")

    if cik:
        subs = client.get_submissions(cik)
        name = subs.get("name", "unknown")
        recent = subs.get("filings", {}).get("recent", {})
        forms  = recent.get("form", [])
        print(f"  {name}: {len(forms)} recent filings")
        print("  Last 5:", forms[:5])

    print("\nEdgarClient OK")
