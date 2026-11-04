"""SQLite storage. Schema is kept portable so it can move to PostgreSQL:

* plain TEXT / INTEGER / REAL columns, ISO-8601 UTC timestamps as TEXT
* natural keys (CIK, accession) as primary keys; surrogate ``id`` columns use
  ``INTEGER PRIMARY KEY`` here and map to ``BIGSERIAL`` / ``GENERATED ... AS IDENTITY`` in PG
* no SQLite-only features (no AUTOINCREMENT, no WITHOUT ROWID, no JSON1)
* ``?`` placeholders are the only dialect difference in queries (``%s`` for psycopg)
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sqlite3
from typing import Any, Iterable

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS companies (
    cik             INTEGER PRIMARY KEY,
    ticker          TEXT NOT NULL,
    name            TEXT NOT NULL DEFAULT '',
    last_crawled_at TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_companies_ticker ON companies (ticker);

CREATE TABLE IF NOT EXISTS filings (
    accession           TEXT PRIMARY KEY,
    cik                 INTEGER NOT NULL REFERENCES companies (cik),
    form                TEXT NOT NULL,
    base_form           TEXT NOT NULL,
    is_amendment        INTEGER NOT NULL DEFAULT 0,
    version             INTEGER NOT NULL DEFAULT 1,
    amends_accession    TEXT,
    filing_date         TEXT NOT NULL,
    report_date         TEXT,
    acceptance_datetime TEXT,
    items               TEXT,
    primary_document    TEXT,
    primary_doc_url     TEXT,
    index_url           TEXT,
    sha256              TEXT,
    status              TEXT NOT NULL DEFAULT 'discovered',
    error               TEXT,
    first_seen_at       TEXT NOT NULL,
    fetched_at          TEXT
);
CREATE INDEX IF NOT EXISTS ix_filings_cik_form ON filings (cik, base_form, filing_date);

CREATE TABLE IF NOT EXISTS documents (
    id           INTEGER PRIMARY KEY,
    accession    TEXT NOT NULL REFERENCES filings (accession),
    kind         TEXT NOT NULL,
    filename     TEXT NOT NULL,
    url          TEXT NOT NULL,
    local_path   TEXT NOT NULL,
    sha256       TEXT NOT NULL,
    size_bytes   INTEGER NOT NULL,
    content_type TEXT,
    deduplicated INTEGER NOT NULL DEFAULT 0,
    fetched_at   TEXT NOT NULL,
    UNIQUE (accession, kind, sha256)
);
CREATE INDEX IF NOT EXISTS ix_documents_sha ON documents (sha256);

CREATE TABLE IF NOT EXISTS sections (
    accession  TEXT NOT NULL REFERENCES filings (accession),
    key        TEXT NOT NULL,
    item       TEXT NOT NULL,
    title      TEXT NOT NULL,
    text       TEXT NOT NULL,
    char_count INTEGER NOT NULL,
    PRIMARY KEY (accession, key)
);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id            INTEGER PRIMARY KEY,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    tickers       TEXT NOT NULL,
    forms         TEXT NOT NULL,
    discovered    INTEGER NOT NULL DEFAULT 0,
    new_filings   INTEGER NOT NULL DEFAULT 0,
    amendments    INTEGER NOT NULL DEFAULT 0,
    errors        INTEGER NOT NULL DEFAULT 0,
    request_count INTEGER NOT NULL DEFAULT 0
);
"""


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


class Store:
    def __init__(self, db_path: str | pathlib.Path):
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            pathlib.Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.execute(
            "INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # -- helpers -----------------------------------------------------------------
    def _one(self, sql: str, params: Iterable[Any] = ()) -> dict | None:
        row = self.conn.execute(sql, tuple(params)).fetchone()
        return dict(row) if row else None

    def _all(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        return [dict(r) for r in self.conn.execute(sql, tuple(params)).fetchall()]

    # -- companies -----------------------------------------------------------------
    def upsert_company(self, cik: int, ticker: str, name: str) -> None:
        now = utcnow()
        self.conn.execute(
            """INSERT INTO companies (cik, ticker, name, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (cik) DO UPDATE SET ticker = excluded.ticker,
                   name = CASE WHEN excluded.name <> '' THEN excluded.name ELSE companies.name END,
                   updated_at = excluded.updated_at""",
            (cik, ticker, name, now, now),
        )
        self.conn.commit()

    def touch_company(self, cik: int) -> None:
        self.conn.execute("UPDATE companies SET last_crawled_at = ? WHERE cik = ?", (utcnow(), cik))
        self.conn.commit()

    def get_company(self, ticker: str) -> dict | None:
        # Tickers can move between CIKs over time; the most recently refreshed row wins.
        return self._one("SELECT * FROM companies WHERE ticker = ? ORDER BY updated_at DESC LIMIT 1",
                         (ticker.strip().upper().replace(".", "-"),))

    def list_companies(self) -> list[dict]:
        return self._all(
            """SELECT c.cik, c.ticker, c.name, c.last_crawled_at, COUNT(f.accession) AS filings,
                      MAX(f.filing_date) AS latest_filing_date
               FROM companies c LEFT JOIN filings f ON f.cik = c.cik
               GROUP BY c.cik, c.ticker, c.name, c.last_crawled_at ORDER BY c.ticker"""
        )

    # -- filings -----------------------------------------------------------------
    def fetched_accessions(self, cik: int) -> set[str]:
        rows = self.conn.execute(
            "SELECT accession FROM filings WHERE cik = ? AND status = 'fetched'", (cik,)
        ).fetchall()
        return {r[0] for r in rows}

    def known_accessions(self, cik: int) -> set[str]:
        rows = self.conn.execute("SELECT accession FROM filings WHERE cik = ?", (cik,)).fetchall()
        return {r[0] for r in rows}

    def upsert_filing(self, ref, version: int, amends: str | None) -> None:
        self.conn.execute(
            """INSERT INTO filings (accession, cik, form, base_form, is_amendment, version,
                   amends_accession, filing_date, report_date, acceptance_datetime, items,
                   primary_document, primary_doc_url, index_url, first_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (accession) DO UPDATE SET version = excluded.version,
                   amends_accession = excluded.amends_accession""",
            (ref.accession, ref.cik, ref.form, ref.base_form, int(ref.is_amendment), version,
             amends, ref.filing_date, ref.report_date or None, ref.acceptance_datetime or None,
             ref.items or None, ref.raw_primary_document, ref.primary_doc_url, ref.index_url,
             utcnow()),
        )
        self.conn.commit()

    def mark_fetched(self, accession: str, sha256: str) -> None:
        self.conn.execute(
            "UPDATE filings SET status = 'fetched', sha256 = ?, error = NULL, fetched_at = ? WHERE accession = ?",
            (sha256, utcnow(), accession),
        )
        self.conn.commit()

    def mark_error(self, accession: str, error: str) -> None:
        self.conn.execute(
            "UPDATE filings SET status = 'error', error = ? WHERE accession = ?", (error[:2000], accession)
        )
        self.conn.commit()

    def list_filings(self, cik: int, form: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
        sql = "SELECT * FROM filings WHERE cik = ?"
        params: list[Any] = [cik]
        if form:
            sql += " AND base_form = ?"
            params.append(form.upper()[:-2] if form.upper().endswith("/A") else form.upper())
        sql += " ORDER BY filing_date DESC, acceptance_datetime DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        return self._all(sql, params)

    def get_filing(self, accession: str) -> dict | None:
        return self._one("SELECT * FROM filings WHERE accession = ?", (accession,))

    def amendments_of(self, accession: str) -> list[dict]:
        return self._all(
            "SELECT accession, form, version, filing_date FROM filings WHERE amends_accession = ? ORDER BY version",
            (accession,),
        )

    # -- documents -----------------------------------------------------------------
    def find_document_by_sha(self, sha256: str) -> dict | None:
        return self._one("SELECT * FROM documents WHERE sha256 = ? ORDER BY id LIMIT 1", (sha256,))

    def add_document(self, accession: str, kind: str, filename: str, url: str, local_path: str,
                     sha256: str, size_bytes: int, content_type: str | None, deduplicated: bool) -> None:
        self.conn.execute(
            """INSERT INTO documents (accession, kind, filename, url, local_path, sha256, size_bytes,
                   content_type, deduplicated, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (accession, kind, sha256) DO NOTHING""",
            (accession, kind, filename, url, local_path, sha256, size_bytes, content_type,
             int(deduplicated), utcnow()),
        )
        self.conn.commit()

    def documents_for(self, accession: str) -> list[dict]:
        return self._all("SELECT * FROM documents WHERE accession = ? ORDER BY id", (accession,))

    # -- sections -----------------------------------------------------------------
    def save_sections(self, accession: str, sections: list[dict]) -> None:
        self.conn.execute("DELETE FROM sections WHERE accession = ?", (accession,))
        self.conn.executemany(
            "INSERT INTO sections (accession, key, item, title, text, char_count) VALUES (?, ?, ?, ?, ?, ?)",
            [(accession, s["key"], s["item"], s["title"], s["text"], len(s["text"])) for s in sections],
        )
        self.conn.commit()

    def sections_for(self, accession: str, include_text: bool = False) -> list[dict]:
        cols = "key, item, title, char_count" + (", text" if include_text else "")
        return self._all(f"SELECT {cols} FROM sections WHERE accession = ? ORDER BY rowid", (accession,))

    def get_section(self, accession: str, key: str) -> dict | None:
        return self._one("SELECT * FROM sections WHERE accession = ? AND key = ?", (accession, key))

    # -- runs ---------------------------------------------------------------------
    def start_run(self, tickers: list[str], forms: Iterable[str]) -> int:
        cur = self.conn.execute(
            "INSERT INTO crawl_runs (started_at, tickers, forms) VALUES (?, ?, ?)",
            (utcnow(), ",".join(tickers), ",".join(forms)),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_run(self, run_id: int, **counts: int) -> None:
        cols = ", ".join(f"{k} = ?" for k in counts)
        self.conn.execute(
            f"UPDATE crawl_runs SET finished_at = ?, {cols} WHERE id = ?",
            (utcnow(), *counts.values(), run_id),
        )
        self.conn.commit()

    def last_run(self) -> dict | None:
        return self._one("SELECT * FROM crawl_runs ORDER BY id DESC LIMIT 1")
