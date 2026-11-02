"""
watchlist_manager.py — Persistent ticker watchlist with sectors, priorities, and notes.

SQLite-backed. Supports CSV import/export, sector grouping, and priority filtering.

Usage:
    wm = WatchlistManager()
    wm.add("NVDA", sector="Technology", priority="HIGH", notes="AI chip leader")
    wm.add("JPM",  sector="Financials",  priority="MEDIUM")
    for entry in wm.get_by_sector("Technology"):
        print(entry)
"""

from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


VALID_PRIORITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


@dataclass
class WatchlistEntry:
    ticker: str
    sector: str = "Unknown"
    priority: str = "MEDIUM"
    notes: str = ""
    added_at: str = ""
    updated_at: str = ""
    tags: str = ""         # comma-separated tags

    def __post_init__(self):
        self.ticker   = self.ticker.upper()
        self.priority = self.priority.upper()
        if self.priority not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority '{self.priority}'. Choose from {VALID_PRIORITIES}")

    def to_dict(self) -> dict:
        return asdict(self)

    def __str__(self):
        return (f"[{self.priority}] {self.ticker:6s}  {self.sector:25s}  "
                f"{self.notes[:50]}")


class WatchlistManager:
    """
    Manages a persistent watchlist of tickers in SQLite.

    Schema:
      watchlist(ticker PK, sector, priority, notes, added_at, updated_at, tags)
    """

    def __init__(self, db_path: Path = Path("data/watchlist.db")):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    ticker      TEXT PRIMARY KEY,
                    sector      TEXT DEFAULT 'Unknown',
                    priority    TEXT DEFAULT 'MEDIUM',
                    notes       TEXT DEFAULT '',
                    added_at    TEXT,
                    updated_at  TEXT,
                    tags        TEXT DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_sector   ON watchlist(sector);
                CREATE INDEX IF NOT EXISTS idx_priority ON watchlist(priority);
            """)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_entry(self, row) -> WatchlistEntry:
        return WatchlistEntry(**dict(row))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, ticker: str, sector: str = "Unknown", priority: str = "MEDIUM",
            notes: str = "", tags: str = "") -> WatchlistEntry:
        """Add a ticker. Raises ValueError on duplicate."""
        entry = WatchlistEntry(
            ticker=ticker, sector=sector, priority=priority,
            notes=notes, tags=tags,
            added_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO watchlist (ticker, sector, priority, notes, added_at, updated_at, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (entry.ticker, entry.sector, entry.priority, entry.notes,
                 entry.added_at, entry.updated_at, entry.tags),
            )
        return entry

    def add_or_update(self, ticker: str, **kwargs) -> WatchlistEntry:
        """Add or upsert a ticker."""
        if self.get(ticker):
            return self.update(ticker, **kwargs)
        return self.add(ticker, **kwargs)

    def remove(self, ticker: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM watchlist WHERE ticker=?", (ticker.upper(),))
            return cur.rowcount > 0

    def update(self, ticker: str, **kwargs) -> Optional[WatchlistEntry]:
        """Update fields. Supported: sector, priority, notes, tags."""
        ticker = ticker.upper()
        allowed = {"sector", "priority", "notes", "tags"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return self.get(ticker)
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [ticker]
        with self._conn() as conn:
            conn.execute(f"UPDATE watchlist SET {set_clause} WHERE ticker=?", values)
        return self.get(ticker)

    def get(self, ticker: str) -> Optional[WatchlistEntry]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM watchlist WHERE ticker=?", (ticker.upper(),)
            ).fetchone()
        return self._row_to_entry(row) if row else None

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_all(self, sort_by: str = "priority") -> list:
        """List all entries. sort_by: 'ticker' | 'priority' | 'sector' | 'added_at'."""
        with self._conn() as conn:
            rows = conn.execute(f"SELECT * FROM watchlist ORDER BY {sort_by}").fetchall()
        entries = [self._row_to_entry(r) for r in rows]
        if sort_by == "priority":
            entries.sort(key=lambda e: PRIORITY_ORDER.get(e.priority, 99))
        return entries

    def get_by_sector(self, sector: str) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM watchlist WHERE LOWER(sector)=LOWER(?) ORDER BY priority",
                (sector,)
            ).fetchall()
        return sorted(
            [self._row_to_entry(r) for r in rows],
            key=lambda e: PRIORITY_ORDER.get(e.priority, 99),
        )

    def get_by_priority(self, priority: str) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM watchlist WHERE priority=? ORDER BY ticker",
                (priority.upper(),)
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def search(self, query: str) -> list:
        """Search ticker, sector, notes, and tags."""
        q = f"%{query.lower()}%"
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM watchlist WHERE
                   LOWER(ticker) LIKE ? OR LOWER(sector) LIKE ?
                   OR LOWER(notes) LIKE ? OR LOWER(tags) LIKE ?""",
                (q, q, q, q)
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def tickers(self) -> list:
        with self._conn() as conn:
            rows = conn.execute("SELECT ticker FROM watchlist ORDER BY ticker").fetchall()
        return [r["ticker"] for r in rows]

    def sectors(self) -> dict:
        """Return {sector: count}."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT sector, COUNT(*) as cnt FROM watchlist GROUP BY sector ORDER BY cnt DESC"
            ).fetchall()
        return {r["sector"]: r["cnt"] for r in rows}

    def count(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------

    def export_csv(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        entries = self.list_all()
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "ticker", "sector", "priority", "notes", "tags", "added_at", "updated_at"
            ])
            writer.writeheader()
            writer.writerows([e.to_dict() for e in entries])

    def import_csv(self, path: Path, overwrite: bool = False) -> int:
        """Import from CSV. Returns number of rows imported."""
        count = 0
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ticker = row.get("ticker", "").strip()
                if not ticker:
                    continue
                if overwrite:
                    self.add_or_update(ticker, **{k: v for k, v in row.items() if k != "ticker"})
                else:
                    try:
                        self.add(ticker, **{k: v for k, v in row.items()
                                            if k in {"sector", "priority", "notes", "tags"}})
                    except sqlite3.IntegrityError:
                        pass
                count += 1
        return count

    def export_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump([e.to_dict() for e in self.list_all()], f, indent=2)

    def import_json(self, path: Path, overwrite: bool = False) -> int:
        with open(path) as f:
            data = json.load(f)
        count = 0
        for row in data:
            ticker = row.pop("ticker", "").strip()
            if not ticker:
                continue
            if overwrite:
                self.add_or_update(ticker, **row)
            else:
                try:
                    self.add(ticker, **{k: v for k, v in row.items()
                                        if k in {"sector", "priority", "notes", "tags"}})
                except sqlite3.IntegrityError:
                    pass
            count += 1
        return count


# ---------------------------------------------------------------------------
# Pre-seeded sample watchlist builder
# ---------------------------------------------------------------------------

SAMPLE_WATCHLIST = [
    ("NVDA", "Technology",     "CRITICAL", "AI GPU leader — monitor supply chain + export controls"),
    ("AAPL", "Technology",     "HIGH",     "Consumer electronics + services"),
    ("MSFT", "Technology",     "HIGH",     "Cloud + AI"),
    ("META", "Technology",     "MEDIUM",   "Social media advertising"),
    ("GOOGL","Technology",     "MEDIUM",   "Search + cloud"),
    ("AMZN", "Technology",     "MEDIUM",   "E-commerce + AWS"),
    ("JPM",  "Financials",     "HIGH",     "Largest US bank — credit risk"),
    ("BAC",  "Financials",     "MEDIUM",   "Consumer banking exposure"),
    ("GS",   "Financials",     "MEDIUM",   "Investment banking"),
    ("XOM",  "Energy",         "HIGH",     "Oil major — sanction risk"),
    ("CVX",  "Energy",         "MEDIUM",   "Oil major"),
    ("LLY",  "Healthcare",     "HIGH",     "GLP-1 drugs — FDA watch"),
    ("JNJ",  "Healthcare",     "MEDIUM",   "Diversified pharma + litigation"),
    ("PFE",  "Healthcare",     "LOW",      "Post-COVID revenue normalization"),
    ("TSLA", "Consumer Disc.", "CRITICAL", "CEO concentration risk"),
    ("F",    "Consumer Disc.", "MEDIUM",   "EV transition + UAW"),
    ("BA",   "Industrials",    "HIGH",     "Boeing — safety + regulatory"),
    ("CAT",  "Industrials",    "LOW",      "Infrastructure cycle"),
    ("SVB",  "Financials",     "CRITICAL", "Resolved — historical monitor"),
]


def seed_sample(wm: WatchlistManager) -> None:
    for ticker, sector, priority, notes in SAMPLE_WATCHLIST:
        wm.add_or_update(ticker, sector=sector, priority=priority, notes=notes)


if __name__ == "__main__":
    wm = WatchlistManager(db_path=Path("data/watchlist_demo.db"))
    seed_sample(wm)
    print(f"Watchlist has {wm.count()} entries")
    print("\nTop CRITICAL / HIGH:")
    for e in wm.get_by_priority("CRITICAL") + wm.get_by_priority("HIGH"):
        print(f"  {e}")
    print("\nSector breakdown:")
    for sector, cnt in wm.sectors().items():
        print(f"  {sector:25s} {cnt}")
