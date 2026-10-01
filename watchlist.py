"""
watchlist.py — 25-company development watchlist.
Mix of large-cap and mid-cap across 4 sectors.
"""

WATCHLIST: list[dict] = [
    # ── Technology ────────────────────────────────────────────────────────────
    {"ticker": "AAPL",  "name": "Apple Inc.",                  "sector": "Technology"},
    {"ticker": "MSFT",  "name": "Microsoft Corporation",       "sector": "Technology"},
    {"ticker": "GOOGL", "name": "Alphabet Inc.",               "sector": "Technology"},
    {"ticker": "NVDA",  "name": "NVIDIA Corporation",          "sector": "Technology"},
    {"ticker": "AMD",   "name": "Advanced Micro Devices",      "sector": "Technology"},
    {"ticker": "CRM",   "name": "Salesforce Inc.",             "sector": "Technology"},
    {"ticker": "NOW",   "name": "ServiceNow Inc.",             "sector": "Technology"},

    # ── Financials ────────────────────────────────────────────────────────────
    {"ticker": "JPM",   "name": "JPMorgan Chase & Co.",        "sector": "Financials"},
    {"ticker": "GS",    "name": "Goldman Sachs Group",         "sector": "Financials"},
    {"ticker": "MS",    "name": "Morgan Stanley",              "sector": "Financials"},
    {"ticker": "BAC",   "name": "Bank of America",             "sector": "Financials"},
    {"ticker": "BLK",   "name": "BlackRock Inc.",              "sector": "Financials"},
    {"ticker": "SCHW",  "name": "Charles Schwab",              "sector": "Financials"},

    # ── Healthcare ────────────────────────────────────────────────────────────
    {"ticker": "JNJ",   "name": "Johnson & Johnson",           "sector": "Healthcare"},
    {"ticker": "UNH",   "name": "UnitedHealth Group",          "sector": "Healthcare"},
    {"ticker": "PFE",   "name": "Pfizer Inc.",                 "sector": "Healthcare"},
    {"ticker": "ABBV",  "name": "AbbVie Inc.",                 "sector": "Healthcare"},
    {"ticker": "MDT",   "name": "Medtronic plc",               "sector": "Healthcare"},
    {"ticker": "ISRG",  "name": "Intuitive Surgical",          "sector": "Healthcare"},

    # ── Industrials / Energy ──────────────────────────────────────────────────
    {"ticker": "CAT",   "name": "Caterpillar Inc.",            "sector": "Industrials"},
    {"ticker": "HON",   "name": "Honeywell International",     "sector": "Industrials"},
    {"ticker": "BA",    "name": "Boeing Company",              "sector": "Industrials"},
    {"ticker": "XOM",   "name": "Exxon Mobil Corporation",     "sector": "Energy"},
    {"ticker": "CVX",   "name": "Chevron Corporation",         "sector": "Energy"},
    {"ticker": "OXY",   "name": "Occidental Petroleum",        "sector": "Energy"},
]
