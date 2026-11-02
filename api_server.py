"""
api_server.py — FastAPI REST API for the EDGAR Disclosure Monitor.

Exposes filing alerts, news rankings, watchlist management, topic pings,
backtest results, and system health through a documented REST interface.

Run:
    python api_server.py
    # or
    uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload

OpenAPI docs available at: http://localhost:8000/docs
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException, Query, Body
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
    import uvicorn
except ImportError:
    raise ImportError("FastAPI and uvicorn required: pip install fastapi uvicorn")


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="EDGAR Disclosure Monitor API",
    description=(
        "REST API for accessing SEC EDGAR filing alerts, news relevance rankings, "
        "topic pings, watchlist management, and backtest results. "
        "All data is deterministic — no AI summarization."
    ),
    version="1.0.0",
    contact={"name": "EDGAR Monitor", "url": "https://github.com/Krish-1717/edgar-disclosure-monitor"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AlertResponse(BaseModel):
    alert_id: str
    ticker: str
    form_type: str
    score: float
    priority: str
    filing_date: str
    summary: str
    filing_url: str = ""

class NewsArticleResponse(BaseModel):
    rank: int
    title: str
    source: str
    published_at: str
    final_score: float
    matched_keywords: list = []
    url: str = ""

class PingRequest(BaseModel):
    topic: str = Field(..., description="Topic string to monitor, e.g. 'Federal Reserve rate hike'")
    priority: str = Field("MEDIUM", description="CRITICAL | HIGH | MEDIUM | LOW")
    tickers: list = Field(default_factory=list, description="Optional list of ticker symbols")
    user_id: str = Field("default", description="User identifier")

class PingResponse(BaseModel):
    ping_id: str
    topic: str
    priority: str
    keywords: list
    created_at: str

class WatchlistEntryRequest(BaseModel):
    ticker: str
    sector: str = "Unknown"
    priority: str = "MEDIUM"
    notes: str = ""
    tags: str = ""

class WatchlistEntryResponse(BaseModel):
    ticker: str
    sector: str
    priority: str
    notes: str
    added_at: str

class BacktestSummaryResponse(BaseModel):
    total_sources: int
    valid_sources: int
    blocked_sources: int
    pass_rate: float
    run_at: str

class HealthResponse(BaseModel):
    status: str
    version: str
    db_connected: bool
    uptime_seconds: float
    checked_at: str


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

_start_time = datetime.utcnow()
_DB_PATH = Path("data/edgar_index.db")
_PINGS_DB = Path("data/pings.db")
_WATCHLIST_DB = Path("data/watchlist.db")


def _conn(path: Path) -> Optional[sqlite3.Connection]:
    if not path.exists():
        return None
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Routes — Health
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health() -> HealthResponse:
    """System health check. Always returns 200 if the server is running."""
    db_ok = _DB_PATH.exists()
    uptime = (datetime.utcnow() - _start_time).total_seconds()
    return HealthResponse(
        status="ok",
        version="1.0.0",
        db_connected=db_ok,
        uptime_seconds=round(uptime, 1),
        checked_at=datetime.utcnow().isoformat(),
    )


# ---------------------------------------------------------------------------
# Routes — Alerts
# ---------------------------------------------------------------------------

@app.get("/alerts", response_model=list, tags=["Alerts"])
def get_alerts(
    ticker: Optional[str] = Query(None, description="Filter by ticker symbol"),
    form_type: Optional[str] = Query(None, description="Filter by form type: 10-K, 8-K, etc."),
    min_score: float = Query(0.0, description="Minimum risk score (0-1)"),
    limit: int = Query(50, le=500, description="Max results"),
) -> list:
    """
    Retrieve EDGAR filing alerts, optionally filtered by ticker, form type,
    and minimum risk score. Results ordered by score descending.
    """
    conn = _conn(_DB_PATH)
    if conn is None:
        return []
    try:
        query = "SELECT * FROM filings WHERE 1=1"
        params: list = []
        if ticker:
            query += " AND UPPER(ticker)=UPPER(?)"
            params.append(ticker)
        if form_type:
            query += " AND form_type=?"
            params.append(form_type)
        query += " ORDER BY rowid DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()


@app.get("/alerts/{alert_id}", tags=["Alerts"])
def get_alert(alert_id: str) -> dict:
    """Retrieve a single alert by ID."""
    conn = _conn(_DB_PATH)
    if conn is None:
        raise HTTPException(status_code=404, detail="Database not found")
    try:
        row = conn.execute(
            "SELECT * FROM filings WHERE accession=?", (alert_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
        return dict(row)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Routes — News
# ---------------------------------------------------------------------------

@app.get("/news", response_model=list, tags=["News"])
def get_news(
    ticker: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    min_score: float = Query(0.0),
    limit: int = Query(30, le=200),
) -> list:
    """
    Retrieve ranked news articles from the news cache, filtered by ticker
    and/or source. Results ordered by relevance score descending.
    """
    news_db = Path("data/news_cache.db")
    conn = _conn(news_db)
    if conn is None:
        return []
    try:
        query = "SELECT * FROM articles WHERE 1=1"
        params: list = []
        if ticker:
            query += " AND tickers_mentioned LIKE ?"
            params.append(f"%{ticker.upper()}%")
        if source:
            query += " AND source=?"
            params.append(source.lower())
        query += " ORDER BY published_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Routes — Pings
# ---------------------------------------------------------------------------

@app.post("/ping", response_model=PingResponse, tags=["Pings"])
def create_ping(req: PingRequest) -> PingResponse:
    """
    Create a new topic ping. The system will match incoming filings and
    news articles against this query and surface matches as alerts.
    """
    try:
        from topic_pinger import TopicPinger
        pinger = TopicPinger(user_id=req.user_id, db_path=_PINGS_DB)
        ping = pinger.ping(req.topic, priority=req.priority, tickers=req.tickers)
        return PingResponse(
            ping_id=ping.ping_id,
            topic=ping.topic,
            priority=ping.priority,
            keywords=ping.keywords,
            created_at=ping.created_at,
        )
    except ImportError:
        raise HTTPException(status_code=501, detail="topic_pinger module not available")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/ping", tags=["Pings"])
def list_pings(user_id: str = Query("default")) -> list:
    """List all active pings for a user."""
    try:
        from topic_pinger import TopicPinger
        pinger = TopicPinger(user_id=user_id, db_path=_PINGS_DB)
        return [
            {"ping_id": p.ping_id, "topic": p.topic, "priority": p.priority,
             "keywords": p.keywords, "created_at": p.created_at}
            for p in pinger.list_pings()
        ]
    except ImportError:
        raise HTTPException(status_code=501, detail="topic_pinger module not available")


@app.delete("/ping/{ping_id}", tags=["Pings"])
def delete_ping(ping_id: str, user_id: str = Query("default")) -> dict:
    """Delete a ping by ID."""
    try:
        from topic_pinger import TopicPinger
        pinger = TopicPinger(user_id=user_id, db_path=_PINGS_DB)
        ok = pinger.remove_ping(ping_id)
        if not ok:
            raise HTTPException(status_code=404, detail=f"Ping {ping_id} not found")
        return {"deleted": ping_id}
    except ImportError:
        raise HTTPException(status_code=501, detail="topic_pinger module not available")


# ---------------------------------------------------------------------------
# Routes — Watchlist
# ---------------------------------------------------------------------------

@app.get("/watchlist", tags=["Watchlist"])
def get_watchlist(
    sector: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
) -> list:
    """List watchlist entries, optionally filtered by sector or priority."""
    try:
        from watchlist_manager import WatchlistManager
        wm = WatchlistManager(db_path=_WATCHLIST_DB)
        if sector:
            entries = wm.get_by_sector(sector)
        elif priority:
            entries = wm.get_by_priority(priority)
        else:
            entries = wm.list_all()
        return [e.to_dict() for e in entries]
    except ImportError:
        raise HTTPException(status_code=501, detail="watchlist_manager module not available")


@app.post("/watchlist", tags=["Watchlist"])
def add_to_watchlist(req: WatchlistEntryRequest) -> dict:
    """Add a ticker to the watchlist."""
    try:
        from watchlist_manager import WatchlistManager
        wm = WatchlistManager(db_path=_WATCHLIST_DB)
        entry = wm.add_or_update(
            req.ticker, sector=req.sector, priority=req.priority,
            notes=req.notes, tags=req.tags
        )
        return entry.to_dict()
    except ImportError:
        raise HTTPException(status_code=501, detail="watchlist_manager module not available")


@app.delete("/watchlist/{ticker}", tags=["Watchlist"])
def remove_from_watchlist(ticker: str) -> dict:
    """Remove a ticker from the watchlist."""
    try:
        from watchlist_manager import WatchlistManager
        wm = WatchlistManager(db_path=_WATCHLIST_DB)
        ok = wm.remove(ticker)
        if not ok:
            raise HTTPException(status_code=404, detail=f"{ticker} not in watchlist")
        return {"removed": ticker.upper()}
    except ImportError:
        raise HTTPException(status_code=501, detail="watchlist_manager module not available")


# ---------------------------------------------------------------------------
# Routes — Backtest
# ---------------------------------------------------------------------------

@app.get("/backtest", response_model=dict, tags=["Backtest"])
def get_backtest_summary(limit: int = Query(1)) -> dict:
    """Retrieve the most recent backtest result summary."""
    backtest_db = Path("data/backtest_results.db")
    conn = _conn(backtest_db)
    if conn is None:
        return {"message": "No backtest results available. Run news_backtest_validator.py first."}
    try:
        row = conn.execute(
            "SELECT * FROM backtest_runs ORDER BY run_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else {"message": "No runs found."}
    except Exception:
        return {"message": "Backtest table not yet initialized."}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
