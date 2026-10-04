"""
trend_analyzer.py — Disclosure Trend Analysis for EDGAR Disclosure Monitor

Analyzes how a company's disclosure behavior changes over time:
  - Is materiality score trending up (more significant changes) or down?
  - Is burial score increasing (more hidden disclosures)?
  - Are specific sections (Item 1A, 7) getting more or less active?
  - Anomaly detection: filings that are statistical outliers in materiality

Outputs:
  - Per-company trend stats
  - Section-level activity heatmaps
  - Anomaly flags

Usage:
    python trend_analyzer.py --ticker AAPL
    python trend_analyzer.py --all              # all companies
    python trend_analyzer.py --export           # save to data/exports/trends.json
"""
from __future__ import annotations
import argparse
import json
import logging
import math
import pathlib
import sqlite3
import statistics
from typing import Optional

log = logging.getLogger(__name__)

RANK_LABELS = {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "MINIMAL"}


# ── Linear regression helpers ──────────────────────────────────────────────────

def _linear_slope(ys: list[float]) -> float:
    """Simple OLS slope for a time-ordered series (x = index 0,1,2,...)."""
    n = len(ys)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
    den = sum((xs[i] - mean_x) ** 2 for i in range(n))
    return num / den if den else 0.0


def _zscore(val: float, mean: float, std: float) -> float:
    return (val - mean) / std if std else 0.0


def _trend_label(slope: float, threshold: float = 0.5) -> str:
    if slope > threshold:   return "↑ RISING"
    if slope < -threshold:  return "↓ FALLING"
    return "→ STABLE"


# ── Analysis functions ─────────────────────────────────────────────────────────

def analyze_ticker(
    conn: sqlite3.Connection,
    ticker: str,
) -> dict:
    """
    Full trend analysis for one company.
    Returns dict with trends, anomalies, and section-level breakdown.
    """
    ticker = ticker.upper()

    alerts = conn.execute("""
        SELECT a.id, a.filed, a.ranking, a.materiality_score,
               a.burial_score, a.attention_gap, a.summary_items, f.form
        FROM alerts a
        JOIN filings f ON a.new_filing_id = f.id
        WHERE a.ticker = ?
        ORDER BY a.filed
    """, (ticker,)).fetchall()

    if not alerts:
        return {"ticker": ticker, "error": "No alerts found — run pipeline first"}

    mat_series  = [a["materiality_score"] for a in alerts]
    bur_series  = [a["burial_score"]       for a in alerts]
    gap_series  = [a["attention_gap"]      for a in alerts]
    dates       = [a["filed"]              for a in alerts]

    # Slopes (per-filing change on average)
    mat_slope = _linear_slope(mat_series)
    bur_slope = _linear_slope(bur_series)
    gap_slope = _linear_slope(gap_series)

    # Anomalies (z-score > 2.0 on materiality)
    mean_mat = statistics.mean(mat_series)
    std_mat  = statistics.stdev(mat_series) if len(mat_series) > 1 else 0.0
    anomalies = [
        {
            "filed":   alerts[i]["filed"],
            "form":    alerts[i]["form"],
            "ranking": RANK_LABELS.get(alerts[i]["ranking"], "—"),
            "materiality": round(mat_series[i], 1),
            "z_score":     round(_zscore(mat_series[i], mean_mat, std_mat), 2),
        }
        for i in range(len(alerts))
        if abs(_zscore(mat_series[i], mean_mat, std_mat)) > 2.0
    ]

    # Section-level activity (which items changed most)
    section_counts: dict[str, int] = {}
    for a in alerts:
        for s in json.loads(a["summary_items"] or "[]"):
            item = s.get("item", "?")
            section_counts[item] = section_counts.get(item, 0) + 1

    # Rolling window (last 4 alerts vs first 4) to detect acceleration
    first_half = mat_series[:len(mat_series)//2] if len(mat_series) >= 4 else []
    last_half  = mat_series[len(mat_series)//2:] if len(mat_series) >= 4 else []
    acceleration = (
        round(statistics.mean(last_half) - statistics.mean(first_half), 2)
        if first_half and last_half else None
    )

    return {
        "ticker":    ticker,
        "n_alerts":  len(alerts),
        "date_range": f"{dates[0]} → {dates[-1]}",

        "materiality": {
            "latest":   round(mat_series[-1], 2),
            "mean":     round(mean_mat, 2),
            "max":      round(max(mat_series), 2),
            "slope":    round(mat_slope, 4),
            "trend":    _trend_label(mat_slope),
            "acceleration": acceleration,
        },
        "burial": {
            "latest":   round(bur_series[-1], 2),
            "mean":     round(statistics.mean(bur_series), 2),
            "max":      round(max(bur_series), 2),
            "slope":    round(bur_slope, 4),
            "trend":    _trend_label(bur_slope),
        },
        "attention_gap": {
            "latest":   round(gap_series[-1], 2),
            "mean":     round(statistics.mean(gap_series), 2),
            "max":      round(max(gap_series), 2),
            "slope":    round(gap_slope, 4),
            "trend":    _trend_label(gap_slope, threshold=2.0),
        },

        "section_activity": dict(
            sorted(section_counts.items(), key=lambda x: x[1], reverse=True)
        ),

        "anomalous_filings": anomalies,

        "filing_history": [
            {
                "filed":       alerts[i]["filed"],
                "form":        alerts[i]["form"],
                "ranking":     RANK_LABELS.get(alerts[i]["ranking"], "—"),
                "materiality": round(mat_series[i], 1),
                "burial":      round(bur_series[i], 1),
                "gap":         round(gap_series[i], 1),
            }
            for i in range(len(alerts))
        ],
    }


def analyze_all(
    conn: sqlite3.Connection,
    min_alerts: int = 2,
) -> list[dict]:
    """
    Analyze all companies in the watchlist with enough data.
    Returns list sorted by materiality trend (most rising first).
    """
    tickers = [
        r[0] for r in conn.execute(
            "SELECT DISTINCT ticker FROM alerts ORDER BY ticker"
        ).fetchall()
    ]

    results = []
    for ticker in tickers:
        try:
            result = analyze_ticker(conn, ticker)
            if "error" not in result and result["n_alerts"] >= min_alerts:
                results.append(result)
        except Exception as e:
            log.warning("Trend analysis failed for %s: %s", ticker, e)

    # Sort: most steeply rising materiality first
    results.sort(key=lambda r: r["materiality"]["slope"], reverse=True)
    return results


def sector_trend_summary(
    conn: sqlite3.Connection,
) -> dict[str, dict]:
    """
    Aggregate trend stats by sector.
    Returns {sector: {mean_mat, mean_bur, n_companies, rising_companies}}
    """
    companies = conn.execute(
        "SELECT ticker, sector FROM companies ORDER BY sector"
    ).fetchall()

    sector_data: dict[str, list[dict]] = {}
    for c in companies:
        try:
            r = analyze_ticker(conn, c["ticker"])
            if "error" not in r:
                sector_data.setdefault(c["sector"], []).append(r)
        except Exception:
            pass

    summary = {}
    for sector, items in sector_data.items():
        mats = [i["materiality"]["mean"] for i in items]
        burs = [i["burial"]["mean"]       for i in items]
        rising = sum(1 for i in items if i["materiality"]["slope"] > 0.5)
        summary[sector] = {
            "n_companies":     len(items),
            "mean_materiality": round(statistics.mean(mats), 2) if mats else 0,
            "mean_burial":      round(statistics.mean(burs), 2) if burs else 0,
            "rising_companies": rising,
            "tickers": [i["ticker"] for i in items],
        }

    return summary


def print_ticker_report(result: dict) -> None:
    if "error" in result:
        print(f"⚠ {result['ticker']}: {result['error']}")
        return

    print(f"\n{'═'*58}")
    print(f"  {result['ticker']} DISCLOSURE TREND  ({result['date_range']})")
    print(f"{'═'*58}")
    print(f"  Alerts: {result['n_alerts']}")

    m = result["materiality"]
    b = result["burial"]
    g = result["attention_gap"]

    print(f"\n  📊 Materiality  latest={m['latest']}  mean={m['mean']}  {m['trend']}")
    if m.get("acceleration") is not None:
        print(f"     Acceleration (2nd half vs 1st half): {m['acceleration']:+.2f}")

    print(f"  🪦 Burial Score  latest={b['latest']}  mean={b['mean']}  {b['trend']}")
    print(f"  🔍 Attention Gap  latest={g['latest']}  mean={g['mean']}  {g['trend']}")

    secs = result["section_activity"]
    if secs:
        top = list(secs.items())[:5]
        print(f"\n  Hot sections: " + "  ".join(f"Item {k}({v})" for k, v in top))

    if result["anomalous_filings"]:
        print(f"\n  ⚠ Anomalous filings (|z|>2):")
        for a in result["anomalous_filings"]:
            print(f"    {a['filed']}  {a['form']}  [{a['ranking']}]  mat={a['materiality']}  z={a['z_score']}")

    print(f"{'═'*58}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="EDGAR disclosure trend analyzer")
    parser.add_argument("--ticker", help="Single ticker")
    parser.add_argument("--all",    action="store_true", help="Analyze all companies")
    parser.add_argument("--sector", action="store_true", help="Sector-level summary")
    parser.add_argument("--export", help="Save results JSON to this path")
    args = parser.parse_args()

    from database import get_connection, init_db
    conn = get_connection()
    init_db(conn)

    if args.ticker:
        result = analyze_ticker(conn, args.ticker)
        print_ticker_report(result)
        if args.export:
            pathlib.Path(args.export).write_text(json.dumps(result, indent=2))

    elif args.sector:
        summary = sector_trend_summary(conn)
        for sector, s in summary.items():
            print(f"\n{sector}: {s['n_companies']} cos | "
                  f"mat={s['mean_materiality']} bur={s['mean_burial']} "
                  f"rising={s['rising_companies']}/{s['n_companies']}")
        if args.export:
            pathlib.Path(args.export).write_text(json.dumps(summary, indent=2))

    elif args.all:
        results = analyze_all(conn)
        for r in results:
            print_ticker_report(r)
        if args.export:
            pathlib.Path(args.export).write_text(json.dumps(results, indent=2))
    else:
        parser.print_help()

    conn.close()
