-- schema.sql — SQLite schema for edgar-disclosure-monitor
-- Day 1: Core tables. All downstream pipeline steps write here.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ── Companies ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS companies (
    cik          TEXT PRIMARY KEY,           -- 10-digit padded CIK
    ticker       TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    sic          TEXT,                       -- SIC industry code
    sector       TEXT,                       -- human-readable sector label
    added_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Filings ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS filings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cik             TEXT NOT NULL REFERENCES companies(cik),
    ticker          TEXT NOT NULL,
    form_type       TEXT NOT NULL,           -- '10-K', '10-Q'
    filing_date     DATE NOT NULL,
    period_of_report DATE,                   -- fiscal period end
    accession       TEXT NOT NULL UNIQUE,    -- e.g. 0001234567-23-000001
    primary_doc_url TEXT,
    fetched_at      TIMESTAMP,
    UNIQUE(cik, form_type, period_of_report)
);

CREATE INDEX IF NOT EXISTS idx_filings_cik       ON filings(cik);
CREATE INDEX IF NOT EXISTS idx_filings_form_type ON filings(form_type);
CREATE INDEX IF NOT EXISTS idx_filings_date      ON filings(filing_date);

-- ── Documents ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS documents (
    filing_id    INTEGER PRIMARY KEY REFERENCES filings(id),
    raw_html     TEXT,                       -- original HTML from EDGAR
    clean_text   TEXT,                       -- stripped and normalised text
    table_json   TEXT,                       -- tables extracted as JSON (separate from body)
    parsed_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Sections ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sections (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    filing_id    INTEGER NOT NULL REFERENCES filings(id),
    item_key     TEXT NOT NULL,              -- 'item_1', 'item_1a', 'item_7', etc.
    item_label   TEXT,                       -- 'Risk Factors', 'MD&A', etc.
    body_text    TEXT,                       -- section text after segmentation
    char_count   INTEGER,
    UNIQUE(filing_id, item_key)
);

CREATE INDEX IF NOT EXISTS idx_sections_filing ON sections(filing_id);
CREATE INDEX IF NOT EXISTS idx_sections_item   ON sections(item_key);

-- ── Paragraph diffs ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS paragraph_diffs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    new_filing_id   INTEGER NOT NULL REFERENCES filings(id),
    prior_filing_id INTEGER NOT NULL REFERENCES filings(id),
    item_key        TEXT NOT NULL,
    change_type     TEXT NOT NULL CHECK(change_type IN ('added','removed','revised','unchanged')),
    prior_text      TEXT,                    -- NULL for 'added'
    new_text        TEXT,                    -- NULL for 'removed'
    similarity      REAL,                    -- cosine sim from TF-IDF alignment
    word_diff_json  TEXT,                    -- difflib output as JSON spans
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_diffs_new_filing ON paragraph_diffs(new_filing_id);
CREATE INDEX IF NOT EXISTS idx_diffs_item       ON paragraph_diffs(item_key);
CREATE INDEX IF NOT EXISTS idx_diffs_type       ON paragraph_diffs(change_type);

-- ── Alerts ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    new_filing_id   INTEGER NOT NULL REFERENCES filings(id),
    diff_id         INTEGER REFERENCES paragraph_diffs(id),
    item_key        TEXT NOT NULL,
    topic_label     TEXT,                    -- LLM classification output
    change_type     TEXT,
    summary         TEXT,                    -- one-sentence LLM summary
    decisive_quote  TEXT,                    -- key phrase identified by LLM
    severity        TEXT,                    -- LLM severity estimate
    materiality_score REAL,                  -- 0–100 raw score
    burial_score    REAL,                    -- 0–100 burial score
    attention_gap   REAL,                    -- materiality / normalised coverage
    alert_level     TEXT CHECK(alert_level IN ('critical','high','relevant','monitor','low_signal')),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alerts_filing ON alerts(new_filing_id);
CREATE INDEX IF NOT EXISTS idx_alerts_level  ON alerts(alert_level);
CREATE INDEX IF NOT EXISTS idx_alerts_topic  ON alerts(topic_label);

-- ── News coverage ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS news_coverage (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    cik          TEXT NOT NULL REFERENCES companies(cik),
    source       TEXT,                       -- 'ir_rss', 'sec_pr', 'gdelt', 'gnews'
    published_at TIMESTAMP,
    title        TEXT,
    url          TEXT UNIQUE,
    cluster_id   INTEGER,                    -- naive title-similarity cluster
    fetched_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_news_cik  ON news_coverage(cik);
CREATE INDEX IF NOT EXISTS idx_news_date ON news_coverage(published_at);

-- ── User feedback ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS feedback (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id   INTEGER NOT NULL REFERENCES alerts(id),
    vote       INTEGER CHECK(vote IN (-1, 1)),  -- thumbs down / up
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Watchlist ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS watchlist (
    ticker     TEXT PRIMARY KEY,
    cik        TEXT REFERENCES companies(cik),
    added_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
