"""
portfolio_tracker.py — Portfolio position tracker for EDGAR filing alerts.

Maintains a SQLite-backed portfolio of ticker positions and cross-references
against EDGAR filing alerts to surface exposure-weighted risk.

Usage:
    tracker = PortfolioTracker()
    tracker.add_position("NVDA", shares=100, cost_basis=450.00, sector="Technology")
    summary = tracker.export_summary()
"""

from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Position:
    ticker: str
    shares: float
    cost_basis: float
    sector: str = "Unknown"
    added_at: str = ""
    notes: str = ""

    @property
    def total_cost(self) -> float:
        return self.shares * self.cost_basis

    def to_dict(self) -> dict:
        d = asdict(self)
        d["total_cost"] = self.total_cost
        return d


@dataclass
class PortfolioAlert:
    ticker: str
    alert_type: str
    summary: str
    score: float
    filing_date: str
    exposure_usd: float
    weighted_score: float


@dataclass
class PortfolioSummary:
    positions: list
    total_positions: int
    total_cost_usd: float
    top_alerts: list
    sector_breakdown: dict
    generated_at: str


class PortfolioTracker:
    """
    Tracks ticker positions in SQLite and correlates them with EDGAR alerts.

    Schema:
      positions(ticker PK, shares, cost_basis, sector, added_at, notes)
      alert_history(id PK, ticker, alert_type, summary, score, filing_date, dispatched_at)
    """

    def __init__(self, db_path: Path = Path("data/portfolio.db")):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS positions (
                    ticker      TEXT PRIMARY KEY,
                    shares      REAL NOT NULL,
                    cost_basis  REAL NOT NULL,
                    sector      TEXT DEFAULT 'Unknown',
                    added_at    TEXT,
                    notes       TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS alert_history (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker       TEXT NOT NULL,
                    alert_type   TEXT,
                    summary      TEXT,
                    score        REAL,
                    filing_date  TEXT,
                    dispatched_at TEXT
                );
            """)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def add_position(self, ticker: str, shares: float, cost_basis: float,
                     sector: str = "Unknown", notes: str = "") -> Position:
        """Add or replace a position."""
        ticker = ticker.upper()
        added_at = datetime.utcnow().isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO positions (ticker, shares, cost_basis, sector, added_at, notes)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(ticker) DO UPDATE SET
                       shares=excluded.shares, cost_basis=excluded.cost_basis,
                       sector=excluded.sector, notes=excluded.notes""",
                (ticker, shares, cost_basis, sector, added_at, notes),
            )
        return Position(ticker, shares, cost_basis, sector, added_at, notes)

    def remove_position(self, ticker: str) -> bool:
        ticker = ticker.upper()
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM positions WHERE ticker=?", (ticker,))
            return cur.rowcount > 0

    def update_shares(self, ticker: str, shares: float) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE positions SET shares=? WHERE ticker=?", (shares, ticker.upper())
            )
            return cur.rowcount > 0

    def get_position(self, ticker: str) -> Optional[Position]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM positions WHERE ticker=?", (ticker.upper(),)
            ).fetchone()
        return Position(**dict(row)) if row else None

    def list_positions(self) -> list:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM positions ORDER BY ticker").fetchall()
        return [Position(**dict(r)) for r in rows]

    def get_exposure(self) -> dict:
        return {p.ticker: p.total_cost for p in self.list_positions()}

    def total_portfolio_value(self) -> float:
        return sum(self.get_exposure().values())

    def sector_weights(self) -> dict:
        positions = self.list_positions()
        total = sum(p.total_cost for p in positions) or 1.0
        sectors: dict = {}
        for p in positions:
            sectors[p.sector] = sectors.get(p.sector, 0.0) + (p.total_cost / total * 100)
        return {k: round(v, 2) for k, v in sorted(sectors.items(), key=lambda x: -x[1])}

    def get_alerts_for_portfolio(self, alerts: list, min_score: float = 0.0) -> list:
        """
        Cross-reference raw alert dicts against held positions.
        Each alert dict: {ticker, alert_type, summary, score, filing_date}.
        Returns PortfolioAlert list sorted by weighted_score desc.
        """
        exposure = self.get_exposure()
        total = self.total_portfolio_value() or 1.0
        tickers_held = set(exposure.keys())
        results = []
        for a in alerts:
            ticker = a.get("ticker", "").upper()
            if ticker not in tickers_held:
                continue
            score = float(a.get("score", 0.0))
            if score < min_score:
                continue
            exp = exposure[ticker]
            weight = exp / total
            results.append(PortfolioAlert(
                ticker=ticker,
                alert_type=a.get("alert_type", ""),
                summary=a.get("summary", ""),
                score=score,
                filing_date=a.get("filing_date", ""),
                exposure_usd=exp,
                weighted_score=round(score * weight, 6),
            ))
        results.sort(key=lambda x: -x.weighted_score)
        return results

    def record_alert(self, ticker: str, alert_type: str, summary: str,
                     score: float, filing_date: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO alert_history
                   (ticker, alert_type, summary, score, filing_date, dispatched_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (ticker.upper(), alert_type, summary, score, filing_date,
                 datetime.utcnow().isoformat()),
            )

    def get_alert_history(self, ticker: Optional[str] = None, limit: int = 100) -> list:
        with self._conn() as conn:
            if ticker:
                rows = conn.execute(
                    "SELECT * FROM alert_history WHERE ticker=? ORDER BY dispatched_at DESC LIMIT ?",
                    (ticker.upper(), limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM alert_history ORDER BY dispatched_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def export_summary(self, output_path: Optional[Path] = None) -> PortfolioSummary:
        positions = self.list_positions()
        total = sum(p.total_cost for p in positions)
        history = self.get_alert_history(limit=20)
        top_alerts = [
            PortfolioAlert(
                ticker=h["ticker"], alert_type=h["alert_type"],
                summary=h["summary"], score=h["score"],
                filing_date=h["filing_date"],
                exposure_usd=self.get_exposure().get(h["ticker"], 0.0),
                weighted_score=h["score"],
            )
            for h in history
        ]
        summary = PortfolioSummary(
            positions=positions,
            total_positions=len(positions),
            total_cost_usd=round(total, 2),
            top_alerts=top_alerts,
            sector_breakdown=self.sector_weights(),
            generated_at=datetime.utcnow().isoformat(),
        )
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                json.dump({
                    "positions": [p.to_dict() for p in summary.positions],
                    "total_positions": summary.total_positions,
                    "total_cost_usd": summary.total_cost_usd,
                    "sector_breakdown": summary.sector_breakdown,
                    "top_alerts": [asdict(a) for a in summary.top_alerts],
                    "generated_at": summary.generated_at,
                }, f, indent=2)
        return summary

    def export_csv(self, output_path: Path) -> None:
        positions = self.list_positions()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "ticker", "shares", "cost_basis", "total_cost", "sector", "added_at", "notes"
            ])
            writer.writeheader()
            for p in positions:
                writer.writerow(p.to_dict())


if __name__ == "__main__":
    tracker = PortfolioTracker(db_path=Path("data/portfolio_demo.db"))
    tracker.add_position("NVDA", 100, 450.00, "Technology", "AI leader")
    tracker.add_position("JPM",  200, 195.00, "Financials",  "Large bank")
    tracker.add_position("XOM",  150, 110.00, "Energy",      "Oil major")
    tracker.add_position("META",  50, 500.00, "Technology",  "Social media")
    tracker.add_position("TSLA",  75, 250.00, "Consumer Discretionary")
    print(f"Portfolio value: ${tracker.total_portfolio_value():,.2f}")
    print(f"Sector weights: {tracker.sector_weights()}")
    mock_alerts = [
        {"ticker": "NVDA", "alert_type": "8-K", "summary": "Earnings beat",
         "score": 0.72, "filing_date": "2026-10-01"},
        {"ticker": "JPM", "alert_type": "10-Q", "summary": "Loan loss provisions up",
         "score": 0.58, "filing_date": "2026-10-02"},
    ]
    for a in tracker.get_alerts_for_portfolio(mock_alerts):
        print(f"[{a.ticker}] score={a.score:.2f} exposure=${a.exposure_usd:,.0f} weighted={a.weighted_score:.4f}")
