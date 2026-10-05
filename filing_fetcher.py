"""
filing_fetcher.py — Clean abstraction over SEC EDGAR for fetching filing metadata.

Provides:
    FilingMeta  — dataclass with per-filing info
    get_two_most_recent(ticker, form_type) -> (old, new) FilingMeta pair
    FilingFetcher class with CIK caching

Usage:
    python filing_fetcher.py  # demo with AAPL
"""
from __future__ import annotations

import json
import pathlib
import time
from dataclasses import dataclass
from typing import Optional
import urllib.request
import urllib.error

USER_AGENT = "EDGAR-Monitor/2.0 (research; patelkrish1717@gmail.com)"
CACHE_PATH = pathlib.Path("data/cik_cache.json")


@dataclass
class FilingMeta:
    ticker: str
    cik: str
    accession: str
    form_type: str
    filed_date: str
    doc_url: str


class FilingFetcher:
    """Fetch SEC EDGAR filing metadata with CIK caching and rate limiting."""

    def __init__(self, user_agent: str = USER_AGENT, cache_path: pathlib.Path = CACHE_PATH):
        self.user_agent = user_agent
        self.cache_path = cache_path
        self._cik_cache: dict[str, str] = self._load_cache()

    # ── Cache helpers ───────────────────────────────────────────────────────

    def _load_cache(self) -> dict[str, str]:
        if self.cache_path.exists():
            try:
                return json.loads(self.cache_path.read_text())
            except Exception:
                return {}
        return {}

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self._cik_cache, indent=2))

    # ── HTTP helper ─────────────────────────────────────────────────────────

    def _get(self, url: str) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()

    def _get_json(self, url: str) -> dict:
        data = self._get(url)
        time.sleep(0.1)
        return json.loads(data)

    # ── CIK resolution ──────────────────────────────────────────────────────

    def resolve_cik(self, ticker: str) -> str:
        """Return zero-padded 10-digit CIK for ticker."""
        t = ticker.upper()
        if t in self._cik_cache:
            return self._cik_cache[t]

        # Use the SEC company-facts endpoint which maps ticker → CIK
        url = "https://www.sec.gov/files/company_tickers.json"
        try:
            data = self._get_json(url)
            for entry in data.values():
                if entry.get("ticker", "").upper() == t:
                    cik = str(entry["cik_str"]).zfill(10)
                    self._cik_cache[t] = cik
                    self._save_cache()
                    return cik
        except Exception as exc:
            raise ValueError(f"Could not resolve CIK for {ticker}: {exc}") from exc

        raise ValueError(f"Ticker {ticker} not found in SEC company list")

    # ── Filing metadata fetch ───────────────────────────────────────────────

    def get_filings(self, ticker: str, form_type: str = "10-K") -> list[FilingMeta]:
        """Return list of FilingMeta sorted newest-first."""
        cik = self.resolve_cik(ticker)
        cik_stripped = cik.lstrip("0") or "0"

        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        data = self._get_json(url)

        filings_data = data.get("filings", {}).get("recent", {})
        forms = filings_data.get("form", [])
        accessions = filings_data.get("accessionNumber", [])
        dates = filings_data.get("filingDate", [])
        primary_docs = filings_data.get("primaryDocument", [])

        results: list[FilingMeta] = []
        for form, acc, date, doc in zip(forms, accessions, dates, primary_docs):
            # Normalize form_type matching (10-K, 10-K/A, 10-Q, 10-Q/A)
            if not form.startswith(form_type):
                continue
            acc_clean = acc.replace("-", "")
            doc_url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/"
                f"{acc_clean}/{doc}"
            )
            results.append(FilingMeta(
                ticker=ticker.upper(),
                cik=cik,
                accession=acc,
                form_type=form,
                filed_date=date,
                doc_url=doc_url,
            ))

        # newest first
        results.sort(key=lambda x: x.filed_date, reverse=True)
        return results

    def get_two_most_recent(
        self, ticker: str, form_type: str = "10-K"
    ) -> tuple[FilingMeta, FilingMeta]:
        """Return (older, newer) pair of the 2 most recent filings."""
        filings = self.get_filings(ticker, form_type)
        if len(filings) < 2:
            raise ValueError(
                f"Need ≥2 {form_type} filings for {ticker}; found {len(filings)}"
            )
        newer, older = filings[0], filings[1]
        return older, newer


# Module-level convenience function
def get_two_most_recent(
    ticker: str, form_type: str = "10-K"
) -> tuple[FilingMeta, FilingMeta]:
    """Module-level shortcut: return (older, newer) FilingMeta pair."""
    return FilingFetcher().get_two_most_recent(ticker, form_type)


if __name__ == "__main__":
    print("Demo: fetching 2 most recent AAPL 10-K filings...")
    fetcher = FilingFetcher()
    old, new = fetcher.get_two_most_recent("AAPL", "10-K")
    print(f"  Older : {old.filed_date}  accession={old.accession}")
    print(f"  Newer : {new.filed_date}  accession={new.accession}")
    print(f"  Doc URL (new): {new.doc_url}")
