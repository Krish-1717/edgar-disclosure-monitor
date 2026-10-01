"""
database.py — SQLite schema and helpers for edgar-disclosure-monitor.

Tables:
  companies   — watchlist
  filings     — filing metadata per company
  sections    — extracted section text per filing
  changes     — paragraph-level diffs between comparable filings
  alerts      — scored, ranked change events
"""
from __future__ import annotations
import sqlite3
import pathlib
import contextlib
from typing import Iterator

DB_PATH = pathlib.Path("data/edgar.db")


def get_connection(db_path: pathlib.Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextlib.contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables if they don't exist."""
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS companies (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker      TEXT NOT NULL UNIQUE,
        name        TEXT,
        sector      TEXT,
        cik         TEXT,
        added_at    TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS filings (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker      TEXT NOT NULL,
        cik         TEXT,
        form        TEXT NOT NULL,
        filed       TEXT NOT NULL,
        period      TEXT,
        accession   TEXT NOT NULL UNIQUE,
        doc_url     TEXT,
        fetched     INTEGER DEFAULT 0,
        raw_html_path   TEXT,
        clean_text_path TEXT,
        FOREIGN KEY (ticker) REFERENCES companies(ticker)
    );

    CREATE TABLE IF NOT EXISTS sections (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        filing_id   INTEGER NOT NULL,
        item        TEXT NOT NULL,
        title       TEXT,
        text        TEXT,
        word_count  INTEGER,
        FOREIGN KEY (filing_id) REFERENCES filings(id),
        UNIQUE (filing_id, item)
    );

    CREATE TABLE IF NOT EXISTS changes (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        new_filing_id   INTEGER NOT NULL,
        old_filing_id   INTEGER NOT NULL,
        item            TEXT NOT NULL,
        change_type     TEXT NOT NULL,   -- 'added' | 'removed' | 'revised' | 'unchanged'
        new_text        TEXT,
        old_text        TEXT,
        similarity      REAL,
        word_delta      INTEGER,
        added_words     INTEGER DEFAULT 0,
        removed_words   INTEGER DEFAULT 0,
        llm_topic       TEXT,
        llm_summary     TEXT,
        llm_severity    TEXT,
        llm_quote       TEXT,
        FOREIGN KEY (new_filing_id) REFERENCES filings(id),
        FOREIGN KEY (old_filing_id) REFERENCES filings(id)
    );

    CREATE TABLE IF NOT EXISTS alerts (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker              TEXT NOT NULL,
        new_filing_id       INTEGER NOT NULL,
        old_filing_id       INTEGER NOT NULL,
        filed               TEXT,
        period              TEXT,
        materiality_score   REAL,
        burial_score        REAL,
        attention_gap       REAL,
        ranking             INTEGER,
        summary_items       TEXT,       -- JSON list of top change summaries
        created_at          TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (new_filing_id) REFERENCES filings(id)
    );

    CREATE INDEX IF NOT EXISTS idx_filings_ticker ON filings(ticker);
    CREATE INDEX IF NOT EXISTS idx_filings_form   ON filings(form);
    CREATE INDEX IF NOT EXISTS idx_alerts_ticker  ON alerts(ticker);
    CREATE INDEX IF NOT EXISTS idx_changes_filing ON changes(new_filing_id);
    """)
    conn.commit()


# ── Query helpers ──────────────────────────────────────────────────────────────

def upsert_company(conn, ticker: str, name: str = "", sector: str = "", cik: str = "") -> None:
    conn.execute("""
        INSERT INTO companies (ticker, name, sector, cik)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET name=excluded.name, sector=excluded.sector, cik=excluded.cik
    """, (ticker, name, sector, cik))


def insert_filing(conn, f: dict) -> int:
    cur = conn.execute("""
        INSERT INTO filings (ticker, cik, form, filed, period, accession, doc_url)
        VALUES (:ticker, :cik, :form, :filed, :period, :accession, :doc_url)
        ON CONFLICT(accession) DO NOTHING
    """, f)
    if cur.lastrowid:
        return cur.lastrowid
    row = conn.execute("SELECT id FROM filings WHERE accession=?", (f["accession"],)).fetchone()
    return row["id"]


def get_prior_comparable_filing(conn, ticker: str, form: str, filed: str) -> sqlite3.Row | None:
    """
    Return the most recent prior filing of the same form type.
    For 10-Q: same quarter one year prior.
    For 10-K: prior year 10-K.
    """
    return conn.execute("""
        SELECT * FROM filings
        WHERE ticker=? AND form=? AND filed < ? AND fetched=1
        ORDER BY filed DESC LIMIT 1
    """, (ticker, form, filed)).fetchone()


def get_sections(conn, filing_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM sections WHERE filing_id=? ORDER BY item", (filing_id,)
    ).fetchall()


def get_alerts(conn, ticker: str | None = None, limit: int = 100) -> list[sqlite3.Row]:
    if ticker:
        return conn.execute("""
            SELECT a.*, f.filed, f.form FROM alerts a
            JOIN filings f ON a.new_filing_id = f.id
            WHERE a.ticker=? ORDER BY a.attention_gap DESC LIMIT ?
        """, (ticker, limit)).fetchall()
    return conn.execute("""
        SELECT a.*, f.filed, f.form FROM alerts a
        JOIN filings f ON a.new_filing_id = f.id
        ORDER BY a.attention_gap DESC LIMIT ?
    """, (limit,)).fetchall()
