# EDGAR Disclosure Monitor

A production-grade SEC filing change-detection system. Ingests 10-K and 10-Q filings from EDGAR, diffs them at the paragraph level against the prior comparable filing, scores each change for materiality and strategic burial, and surfaces alerts ranked by Attention Gap — high-materiality disclosures with low press coverage.

**Stack:** Python 3.11 · requests · BeautifulSoup4 · scikit-learn TF-IDF · SQLite · Streamlit · OpenAI API (classification only) · yfinance (backtest)

---

## How It Works

```mermaid
flowchart TD
    A[SEC EDGAR API\ncompany_tickers.json\nsubmissions/CIK.json] --> B[EDGAR Client\nRate-limited 8 req/sec\nDisk cache · Retry backoff]

    B --> C[Document Fetch\nRaw HTML → Clean Text\nTable isolation]

    C --> D[Section Segmenter\nItem 1A / 7 / 8 / 9A\nTOC suppression · regex]

    D --> E[Paragraph Aligner\nTF-IDF cosine per Item\nGreedy best match]

    E --> F{Similarity\nThreshold}
    F -- ≥ 0.95 --> G[Unchanged]
    F -- 0.50–0.95 --> H[Revised\nword-level difflib]
    F -- < 0.50 --> I[Added / Removed]

    H --> J[Change Scorer]
    I --> J

    J --> K[Materiality Score\n0–100\nVolume · Hedging · Specificity]
    J --> L[Burial Score\n0–100\nPosition · Timing · Boilerplate]

    K --> M[Attention Gap\nMateriality / Coverage]
    L --> M

    M --> N[5-Level Alert Ranking\nCRITICAL → MINIMAL]

    N --> O[SQLite Store\nfilings · sections · changes · alerts]

    O --> P[Streamlit UI\nAlert Feed · Watchlist\nSide-by-Side Diff Viewer]
```

---

## Alert Feed Sample

```
┌──────────────────────────────────────────────────────────────────────┐
│                    EDGAR DISCLOSURE MONITOR                          │
├──────────┬──────┬────────────┬─────────────┬────────────┬───────────┤
│ Ticker   │ Form │ Filed      │ Rank        │ Materiality │ Att. Gap │
├──────────┼──────┼────────────┼─────────────┼────────────┼───────────┤
│ OXY      │ 10-K │ 2024-02-21 │ 🔴 CRITICAL │    78.4    │   156.8  │
│ BA       │ 10-K │ 2024-01-31 │ 🟠 HIGH     │    61.2    │    81.6  │
│ PFE      │ 10-Q │ 2024-11-05 │ 🟠 HIGH     │    58.9    │    58.9  │
│ SCHW     │ 10-Q │ 2024-10-18 │ 🟡 MEDIUM   │    44.1    │    44.1  │
│ MDT      │ 10-K │ 2024-06-25 │ 🔵 LOW      │    22.7    │    22.7  │
└──────────┴──────┴────────────┴─────────────┴────────────┴───────────┘
```

---

## Scoring System

### Materiality Score (0–100)

Computed without an LLM — runs on every paragraph, costs nothing:

```
Score = 0.5 × Volume + 0.3 × Hedging Shift + 0.2 × Specificity Shift

Volume         = (added + revised words) / total section words × 100
Hedging Shift  = Δ risk-language density (may, could, material, adverse…)
Specificity    = Δ count of $amounts, %, named dates, proper nouns

Section weight: Item 1A (×2.0) > Item 7 MD&A (×1.8) > Item 9A (×1.4) > …
```

### Burial Score (0–100)

```
Score = Position percentile (×30) + Section obscurity (×25)
      + Boilerplate ratio (×15) + Filing timing (Friday +20, Thu +10)
```

### Attention Gap

```
Attention Gap = Materiality Score / max(Normalized Press Coverage, 0.01)
```

High Attention Gap = lots changed, nobody noticed.

---

## Paragraph Alignment

The core of the product. Each section is split into paragraphs and aligned against the prior comparable filing (10-K vs prior-year 10-K; 10-Q vs same quarter prior year):

```
TF-IDF cosine similarity matrix → greedy best-match above 0.50 threshold

≥ 0.95  → unchanged (skip)
0.50–0.95 → revised  (run word-level difflib for insertion/deletion spans)
< 0.50  → added or removed
```

---

## Running It

```bash
git clone https://github.com/Krish-1717/edgar-disclosure-monitor
cd edgar-disclosure-monitor
pip install -r requirements.txt

# Ingest a single company
python run_pipeline.py --ticker AAPL

# Ingest multiple tickers
python run_pipeline.py --tickers AAPL MSFT GOOGL NVDA

# Full watchlist (25 companies, ~1 hour first run)
python run_pipeline.py --all

# Launch the UI
streamlit run app.py
```

**SEC User-Agent:** Edit `USER_AGENT` in `run_pipeline.py` with your name and email. Required by SEC — requests without it return 403.

---

## Project Structure

```
edgar-disclosure-monitor/
├── edgar_client.py        # EDGAR API client — rate limiting, cache, retry
├── database.py            # SQLite schema: companies, filings, sections, changes, alerts
├── watchlist.py           # 25-company development watchlist (4 sectors)
├── section_segmenter.py   # Item-level section extraction from HTML → text
├── paragraph_aligner.py   # TF-IDF cosine alignment + word-level difflib
├── change_scorer.py       # Materiality Score, Burial Score, Attention Gap
├── run_pipeline.py        # End-to-end ingestion runner (CLI)
├── app.py                 # Streamlit UI: Alert Feed, Watchlist, Diff Viewer
├── requirements.txt
└── data/
    ├── edgar.db           # SQLite database (created on first run)
    ├── cache/             # HTTP response cache (avoids re-fetching)
    └── filings/           # Clean text per filing
```

---

## Watchlist (25 Companies)

| Sector | Tickers |
|---|---|
| Technology | AAPL, MSFT, GOOGL, NVDA, AMD, CRM, NOW |
| Financials | JPM, GS, MS, BAC, BLK, SCHW |
| Healthcare | JNJ, UNH, PFE, ABBV, MDT, ISRG |
| Industrials / Energy | CAT, HON, BA, XOM, CVX, OXY |

---

## Roadmap

- [ ] LLM classification layer (topic + one-sentence summary per revised paragraph)
- [ ] News ingest + Attention Gap from real coverage counts (GDELT / Google News RSS)
- [ ] Quintile backtest: change score vs forward 5-day returns
- [ ] 8-K and proxy filing support
- [ ] FastAPI backend + React frontend for portfolio version
