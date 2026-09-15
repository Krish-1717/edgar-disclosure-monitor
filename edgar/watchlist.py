"""
watchlist.py — Development universe: 25 companies for Day 1 ingest.

Selection criteria:
  - Mix of large-cap and mid-cap
  - Four sectors: Tech, Financials, Healthcare, Industrials
  - All have filed 10-K and 10-Q regularly since 2019
  - Diverse disclosure styles (wordy vs. terse filers)

This list is hardcoded for Phase 1. No user auth, no dynamic watchlist.
Swap in edgar/watchlist_dynamic.py in Phase 2.
"""

from typing import List, Dict

# 25-company development watchlist
# fmt: off
WATCHLIST: List[Dict] = [
    # ── Technology (7) ──────────────────────────────────────────────────────
    {"ticker": "AAPL",   "name": "Apple Inc.",                   "sector": "Technology"},
    {"ticker": "MSFT",   "name": "Microsoft Corporation",         "sector": "Technology"},
    {"ticker": "GOOGL",  "name": "Alphabet Inc.",                 "sector": "Technology"},
    {"ticker": "META",   "name": "Meta Platforms Inc.",           "sector": "Technology"},
    {"ticker": "NVDA",   "name": "NVIDIA Corporation",            "sector": "Technology"},
    {"ticker": "CRM",    "name": "Salesforce Inc.",               "sector": "Technology"},
    {"ticker": "SNOW",   "name": "Snowflake Inc.",                "sector": "Technology"},  # mid-cap, wordy risk factors

    # ── Financials (6) ──────────────────────────────────────────────────────
    {"ticker": "JPM",    "name": "JPMorgan Chase & Co.",          "sector": "Financials"},
    {"ticker": "BAC",    "name": "Bank of America Corporation",   "sector": "Financials"},
    {"ticker": "GS",     "name": "Goldman Sachs Group Inc.",      "sector": "Financials"},
    {"ticker": "MS",     "name": "Morgan Stanley",                "sector": "Financials"},
    {"ticker": "SCHW",   "name": "Charles Schwab Corporation",    "sector": "Financials"},
    {"ticker": "HOOD",   "name": "Robinhood Markets Inc.",        "sector": "Financials"},  # mid-cap, high-change filer

    # ── Healthcare (6) ──────────────────────────────────────────────────────
    {"ticker": "JNJ",    "name": "Johnson & Johnson",             "sector": "Healthcare"},
    {"ticker": "PFE",    "name": "Pfizer Inc.",                   "sector": "Healthcare"},
    {"ticker": "ABBV",   "name": "AbbVie Inc.",                   "sector": "Healthcare"},
    {"ticker": "UNH",    "name": "UnitedHealth Group Inc.",       "sector": "Healthcare"},
    {"ticker": "MRNA",   "name": "Moderna Inc.",                  "sector": "Healthcare"},  # mid-cap, frequent 10-Q changes
    {"ticker": "TDOC",   "name": "Teladoc Health Inc.",           "sector": "Healthcare"},  # mid-cap

    # ── Industrials / Consumer (6) ───────────────────────────────────────────
    {"ticker": "CAT",    "name": "Caterpillar Inc.",              "sector": "Industrials"},
    {"ticker": "BA",     "name": "Boeing Company",                "sector": "Industrials"},  # high litigation disclosure
    {"ticker": "GE",     "name": "GE Aerospace",                  "sector": "Industrials"},
    {"ticker": "AMZN",   "name": "Amazon.com Inc.",               "sector": "Consumer"},
    {"ticker": "TSLA",   "name": "Tesla Inc.",                    "sector": "Consumer"},    # frequent risk-factor revisions
    {"ticker": "NKE",    "name": "Nike Inc.",                     "sector": "Consumer"},
]
# fmt: on

TICKERS: List[str] = [c["ticker"] for c in WATCHLIST]

SECTOR_MAP: Dict[str, str] = {c["ticker"]: c["sector"] for c in WATCHLIST}

FORM_TYPES = ["10-K", "10-Q"]   # only these; 8-K is Phase 2
MIN_FILING_DATE = "2019-01-01"  # don't ingest anything older


def get_watchlist() -> List[Dict]:
    """Return the full watchlist as a list of dicts."""
    return WATCHLIST


def get_tickers() -> List[str]:
    """Return just the ticker symbols."""
    return TICKERS


if __name__ == "__main__":
    print(f"Development watchlist: {len(WATCHLIST)} companies")
    for sector in sorted(set(SECTOR_MAP.values())):
        companies = [c for c in WATCHLIST if c["sector"] == sector]
        print(f"  {sector}: {', '.join(c['ticker'] for c in companies)}")
