"""
api.py — FastAPI REST Layer for EDGAR Disclosure Monitor

Provides the HTTP endpoints that the Next.js web frontend (and any other client)
can call. Wraps the existing pipeline, database, and enrichment modules.

Endpoints:
  GET  /health                      health check
  GET  /alerts                      paginated alert feed
  GET  /alerts/{id}                 single alert detail + changes
  GET  /watchlist                   company list with filing counts
  GET  /companies/{ticker}/alerts   all alerts for one company
  POST /pipeline/run                trigger pipeline for ticker(s)
  GET  /pipeline/status             last pipeline run status
  POST /waitlist                    join waitlist (email capture)
  GET  /waitlist/approve/{email}    approve a waitlist email (admin)
  GET  /export/alerts.csv           download alerts as CSV
  GET  /export/alert/{id}/diff.json export diff for one alert

Run:
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload

Requires:
    pip install fastapi uvicorn[standard]
"""
from __future__ import annotations
import csv
import io
import json
import logging
import os
import pathlib
import subprocess
import sys
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime, date
from typing import Optional

log = logging.getLogger(__name__)

try:
    from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse, JSONResponse
    from pydantic import BaseModel, EmailStr
    FASTAPI_AVAILABLE = True
except ImportError:
    raise ImportError("FastAPI not installed. Run: pip install fastapi uvicorn[standard]")

from database import get_connection, init_db, get_alerts

DB_PATH = pathlib.Path(os.getenv("DB_PATH", "data/edgar.db"))

RANK_LABELS = {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "MINIMAL"}

# ── Pipeline state (in-memory, not persisted across restarts) ──────────────────
_pipeline_state: dict = {
    "running": False,
    "last_run": None,
    "last_ticker": None,
    "last_returncode": None,
    "last_stderr": "",
}


# ── DB dependency ──────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    conn = get_connection(DB_PATH)
    init_db(conn)
    return conn


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("EDGAR Monitor API starting up")
    conn = get_db()
    init_db(conn)
    conn.close()
    yield
    log.info("EDGAR Monitor API shutting down")


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="EDGAR Disclosure Monitor API",
    description="REST API for SEC filing change detection and ranking",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten this in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic models ────────────────────────────────────────────────────────────

class AlertSummary(BaseModel):
    id: int
    ticker: str
    form: str
    filed: str
    period: Optional[str]
    ranking: int
    rank_label: str
    materiality_score: float
    burial_score: float
    attention_gap: float
    top_sections: list[str]


class AlertDetail(AlertSummary):
    summary_items: list[dict]
    filing_day_return:   Optional[float]
    event_window_return: Optional[float]
    abnormal_return:     Optional[float]
    volume_ratio:        Optional[float]
    price_impact_score:  Optional[float]


class PipelineRequest(BaseModel):
    ticker:  Optional[str] = None   # None = full watchlist
    tickers: Optional[list[str]] = None


class WaitlistRequest(BaseModel):
    email: str
    name:  Optional[str] = None


def _row_to_alert_summary(row: sqlite3.Row) -> dict:
    summary = json.loads(row["summary_items"] or "[]")
    top_sections = [f"Item {s['item']}" for s in summary[:3]]
    return {
        "id":                row["id"],
        "ticker":            row["ticker"],
        "form":              row.get("form") or "10-K/Q",
        "filed":             row["filed"],
        "period":            row.get("period"),
        "ranking":           row["ranking"],
        "rank_label":        RANK_LABELS.get(row["ranking"], "MINIMAL"),
        "materiality_score": round(row["materiality_score"], 2),
        "burial_score":      round(row["burial_score"], 2),
        "attention_gap":     round(row["attention_gap"], 2),
        "top_sections":      top_sections,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/alerts", response_model=list[dict])
def list_alerts(
    ticker:   Optional[str] = None,
    min_rank: int = Query(1, ge=1, le=5),
    limit:    int = Query(50, ge=1, le=500),
    offset:   int = Query(0, ge=0),
    db: sqlite3.Connection = Depends(get_db),
):
    """Return ranked alerts, optionally filtered by ticker and min_rank."""
    query = """
        SELECT a.*, f.form
        FROM alerts a
        JOIN filings f ON a.new_filing_id = f.id
        WHERE a.ranking >= ?
    """
    params: list = [min_rank]
    if ticker:
        query += " AND a.ticker = ?"
        params.append(ticker.upper())
    query += " ORDER BY a.attention_gap DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    rows = db.execute(query, params).fetchall()
    db.close()
    return [_row_to_alert_summary(r) for r in rows]


@app.get("/alerts/{alert_id}")
def get_alert(alert_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Return full alert detail including changes."""
    row = db.execute("""
        SELECT a.*, f.form FROM alerts a
        JOIN filings f ON a.new_filing_id = f.id
        WHERE a.id = ?
    """, (alert_id,)).fetchone()

    if not row:
        db.close()
        raise HTTPException(status_code=404, detail="Alert not found")

    changes = db.execute("""
        SELECT item, change_type, new_text, old_text, similarity,
               word_delta, added_words, removed_words,
               llm_topic, llm_summary, llm_severity, llm_quote
        FROM changes
        WHERE new_filing_id = ? AND change_type != 'unchanged'
        ORDER BY item, rowid
        LIMIT 100
    """, (row["new_filing_id"],)).fetchall()

    result = _row_to_alert_summary(row)
    result["summary_items"]       = json.loads(row["summary_items"] or "[]")
    result["filing_day_return"]   = row["filing_day_return"]   if "filing_day_return"   in row.keys() else None
    result["event_window_return"] = row["event_window_return"] if "event_window_return" in row.keys() else None
    result["abnormal_return"]     = row["abnormal_return"]     if "abnormal_return"     in row.keys() else None
    result["volume_ratio"]        = row["volume_ratio"]        if "volume_ratio"        in row.keys() else None
    result["price_impact_score"]  = row["price_impact_score"]  if "price_impact_score"  in row.keys() else None
    result["changes"] = [dict(c) for c in changes]

    db.close()
    return result


@app.get("/watchlist")
def get_watchlist(db: sqlite3.Connection = Depends(get_db)):
    """Return all companies with filing and alert counts."""
    rows = db.execute("""
        SELECT c.ticker, c.name, c.sector,
               COUNT(DISTINCT f.id)                   AS filings_ingested,
               MAX(f.filed)                           AS last_filed,
               COUNT(DISTINCT a.id)                   AS alert_count,
               ROUND(AVG(a.materiality_score), 1)     AS avg_materiality,
               ROUND(MAX(a.attention_gap), 1)         AS max_gap
        FROM companies c
        LEFT JOIN filings f ON f.ticker = c.ticker AND f.fetched = 1
        LEFT JOIN alerts  a ON a.ticker = c.ticker
        GROUP BY c.ticker
        ORDER BY c.sector, c.ticker
    """).fetchall()
    db.close()
    return [dict(r) for r in rows]


@app.get("/companies/{ticker}/alerts")
def company_alerts(
    ticker: str,
    limit: int = Query(20, ge=1, le=200),
    db: sqlite3.Connection = Depends(get_db),
):
    rows = db.execute("""
        SELECT a.*, f.form FROM alerts a
        JOIN filings f ON a.new_filing_id = f.id
        WHERE a.ticker = ?
        ORDER BY a.filed DESC, a.attention_gap DESC
        LIMIT ?
    """, (ticker.upper(), limit)).fetchall()
    db.close()
    return [_row_to_alert_summary(r) for r in rows]


# ── Pipeline ───────────────────────────────────────────────────────────────────

def _run_pipeline_bg(tickers: list[str] | None):
    global _pipeline_state
    _pipeline_state["running"]     = True
    _pipeline_state["last_run"]    = datetime.utcnow().isoformat()
    _pipeline_state["last_ticker"] = tickers

    args = [sys.executable, "run_pipeline.py"]
    if tickers:
        args += ["--tickers"] + tickers
    else:
        args += ["--all"]

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            cwd=pathlib.Path(__file__).parent,
            timeout=3600,
        )
        _pipeline_state["last_returncode"] = result.returncode
        _pipeline_state["last_stderr"]     = result.stderr[-2000:] if result.stderr else ""
        log.info("Pipeline exited %d", result.returncode)
    except Exception as e:
        _pipeline_state["last_returncode"] = -1
        _pipeline_state["last_stderr"]     = str(e)
        log.error("Pipeline subprocess error: %s", e)
    finally:
        _pipeline_state["running"] = False


@app.post("/pipeline/run", status_code=202)
def trigger_pipeline(req: PipelineRequest, background_tasks: BackgroundTasks):
    """Trigger the ingestion pipeline in the background."""
    if _pipeline_state["running"]:
        raise HTTPException(status_code=409, detail="Pipeline already running")

    tickers = None
    if req.ticker:
        tickers = [req.ticker.upper()]
    elif req.tickers:
        tickers = [t.upper() for t in req.tickers]

    background_tasks.add_task(_run_pipeline_bg, tickers)
    return {"status": "started", "tickers": tickers or "full_watchlist"}


@app.get("/pipeline/status")
def pipeline_status():
    return {**_pipeline_state}


# ── Waitlist ───────────────────────────────────────────────────────────────────

def _ensure_waitlist_table(db: sqlite3.Connection) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS waitlist (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT NOT NULL UNIQUE,
            name       TEXT,
            approved   INTEGER DEFAULT 0,
            joined_at  TEXT DEFAULT (datetime('now')),
            approved_at TEXT
        )
    """)
    db.commit()


@app.post("/waitlist", status_code=201)
def join_waitlist(req: WaitlistRequest, db: sqlite3.Connection = Depends(get_db)):
    """Add an email to the waitlist."""
    _ensure_waitlist_table(db)
    try:
        db.execute(
            "INSERT INTO waitlist (email, name) VALUES (?, ?)",
            (req.email.lower().strip(), req.name),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.close()
        raise HTTPException(status_code=409, detail="Email already on waitlist")

    position = db.execute("SELECT COUNT(*) FROM waitlist").fetchone()[0]
    db.close()
    return {"status": "added", "position": position}


@app.get("/waitlist/position/{email}")
def waitlist_position(email: str, db: sqlite3.Connection = Depends(get_db)):
    """Return queue position for an email."""
    _ensure_waitlist_table(db)
    row = db.execute(
        "SELECT id, approved FROM waitlist WHERE email=?", (email.lower(),)
    ).fetchone()
    if not row:
        db.close()
        raise HTTPException(status_code=404, detail="Email not found")

    position = db.execute(
        "SELECT COUNT(*) FROM waitlist WHERE id <= ?", (row["id"],)
    ).fetchone()[0]
    db.close()
    return {"email": email, "position": position, "approved": bool(row["approved"])}


@app.get("/waitlist/approve/{email}")
def approve_waitlist(email: str, secret: str = Query(...), db: sqlite3.Connection = Depends(get_db)):
    """Admin endpoint: approve a waitlist email. Requires ?secret=ADMIN_SECRET env var."""
    admin_secret = os.getenv("ADMIN_SECRET", "")
    if not admin_secret or secret != admin_secret:
        raise HTTPException(status_code=403, detail="Invalid secret")

    _ensure_waitlist_table(db)
    result = db.execute(
        "UPDATE waitlist SET approved=1, approved_at=datetime('now') WHERE email=?",
        (email.lower(),)
    )
    db.commit()
    db.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Email not found")
    return {"status": "approved", "email": email}


# ── Export ─────────────────────────────────────────────────────────────────────

@app.get("/export/alerts.csv")
def export_alerts_csv(
    min_rank: int = Query(1, ge=1, le=5),
    db: sqlite3.Connection = Depends(get_db),
):
    """Download all alerts as a CSV file."""
    rows = db.execute("""
        SELECT a.ticker, f.form, a.filed, a.period,
               a.ranking, a.materiality_score, a.burial_score, a.attention_gap
        FROM alerts a
        JOIN filings f ON a.new_filing_id = f.id
        WHERE a.ranking >= ?
        ORDER BY a.attention_gap DESC
    """, (min_rank,)).fetchall()
    db.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ticker", "Form", "Filed", "Period",
                     "Rank", "Materiality", "Burial", "AttentionGap"])
    for r in rows:
        writer.writerow([
            r["ticker"], r["form"] or "", r["filed"], r["period"] or "",
            RANK_LABELS.get(r["ranking"], ""), r["materiality_score"],
            r["burial_score"], r["attention_gap"],
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=edgar_alerts.csv"},
    )


@app.get("/export/alert/{alert_id}/diff.json")
def export_diff_json(alert_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Export all changes for an alert as JSON."""
    alert = db.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)).fetchone()
    if not alert:
        db.close()
        raise HTTPException(status_code=404, detail="Alert not found")

    changes = db.execute("""
        SELECT * FROM changes
        WHERE new_filing_id = ? AND change_type != 'unchanged'
        ORDER BY item, rowid
    """, (alert["new_filing_id"],)).fetchall()
    db.close()

    return {
        "alert_id":         alert_id,
        "ticker":           alert["ticker"],
        "filed":            alert["filed"],
        "materiality":      alert["materiality_score"],
        "burial":           alert["burial_score"],
        "attention_gap":    alert["attention_gap"],
        "changes": [dict(c) for c in changes],
    }


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
