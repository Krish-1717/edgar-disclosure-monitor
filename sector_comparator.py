"""
sector_comparator.py — Peer Comparison Engine for EDGAR Disclosure Monitor

Ranks each company's materiality, burial, and attention gap scores
against its sector peers. Surfaces companies that are statistical
outliers — either consistently burying significant changes or being
unusually transparent.

Key outputs:
  - Percentile ranking within sector
  - Sector median / mean / std for each metric
  - "Outlier" flag (>1.5 std from mean)
  - Cross-sector comparison table

Usage:
    python sector_comparator.py --ticker AAPL
    python sector_comparator.py --sector Technology
    python sector_comparator.py --all
    python sector_comparator.py --top-buried          # who buries the most?
"""
from __future__ import annotations
import argparse
import json
import logging
import statistics
from typing import Optional
import sqlite3

log = logging.getLogger(__name__)


# ── Data loading ───────────────────────────────────────────────────────────────

def load_company_stats(conn: sqlite3.Connection) -> list[dict]:
    """
    Return per-company aggregate stats joined with sector info.
    """
    rows = conn.execute("""
        SELECT c.ticker, c.name, c.sector,
               COUNT(DISTINCT a.id)                    AS n_alerts,
               ROUND(AVG(a.materiality_score), 2)      AS avg_materiality,
               ROUND(MAX(a.materiality_score), 2)      AS max_materiality,
               ROUND(AVG(a.burial_score), 2)           AS avg_burial,
               ROUND(MAX(a.burial_score), 2)           AS max_burial,
               ROUND(AVG(a.attention_gap), 2)          AS avg_gap,
               ROUND(MAX(a.attention_gap), 2)          AS max_gap,
               MAX(a.ranking)                          AS max_rank,
               COUNT(CASE WHEN a.ranking >= 4 THEN 1 END) AS high_alert_count
        FROM companies c
        LEFT JOIN alerts a ON a.ticker = c.ticker
        GROUP BY c.ticker
        HAVING n_alerts > 0
        ORDER BY c.sector, avg_materiality DESC
    """).fetchall()
    return [dict(r) for r in rows]


# ── Sector statistics ──────────────────────────────────────────────────────────

def build_sector_stats(companies: list[dict]) -> dict[str, dict]:
    """
    Compute sector-level stats for each metric.
    Returns {sector: {metric: {mean, median, std, min, max, n}}}
    """
    sectors: dict[str, list[dict]] = {}
    for c in companies:
        sectors.setdefault(c["sector"] or "Unknown", []).append(c)

    stats: dict[str, dict] = {}
    for sector, members in sectors.items():
        stats[sector] = {}
        for metric in ("avg_materiality", "avg_burial", "avg_gap"):
            vals = [m[metric] for m in members if m[metric] is not None]
            if not vals:
                stats[sector][metric] = {}
                continue
            stats[sector][metric] = {
                "mean":   round(statistics.mean(vals), 2),
                "median": round(statistics.median(vals), 2),
                "std":    round(statistics.stdev(vals), 2) if len(vals) > 1 else 0.0,
                "min":    round(min(vals), 2),
                "max":    round(max(vals), 2),
                "n":      len(vals),
            }
    return stats


def _percentile_rank(value: float, all_values: list[float]) -> float:
    """Return 0–100 percentile rank of value within all_values."""
    if not all_values:
        return 50.0
    below = sum(1 for v in all_values if v < value)
    return round(below / len(all_values) * 100, 1)


def _outlier_flag(value: float, mean: float, std: float, threshold: float = 1.5) -> str:
    if std == 0:
        return "NORMAL"
    z = (value - mean) / std
    if z > threshold:  return "HIGH_OUTLIER"
    if z < -threshold: return "LOW_OUTLIER"
    return "NORMAL"


# ── Company comparison ─────────────────────────────────────────────────────────

def compare_ticker(
    conn: sqlite3.Connection,
    ticker: str,
) -> dict:
    """
    Full peer comparison for a single company.
    """
    all_companies  = load_company_stats(conn)
    sector_stats   = build_sector_stats(all_companies)

    company = next((c for c in all_companies if c["ticker"] == ticker.upper()), None)
    if not company:
        return {"ticker": ticker, "error": "Company not found or no alerts yet"}

    sector  = company.get("sector") or "Unknown"
    peers   = [c for c in all_companies if c["sector"] == sector]
    ss      = sector_stats.get(sector, {})

    def peer_pct(metric: str) -> float:
        vals = [p[metric] for p in peers if p[metric] is not None]
        return _percentile_rank(company[metric] or 0, vals)

    def outlier(metric: str) -> str:
        m = ss.get(metric, {})
        return _outlier_flag(
            company[metric] or 0,
            m.get("mean", 0), m.get("std", 0)
        )

    return {
        "ticker":  ticker.upper(),
        "name":    company["name"],
        "sector":  sector,
        "n_alerts": company["n_alerts"],
        "sector_peer_count": len(peers),

        "materiality": {
            "value":            company["avg_materiality"],
            "max":              company["max_materiality"],
            "sector_mean":      ss.get("avg_materiality", {}).get("mean"),
            "sector_median":    ss.get("avg_materiality", {}).get("median"),
            "sector_percentile": peer_pct("avg_materiality"),
            "outlier_flag":     outlier("avg_materiality"),
        },
        "burial": {
            "value":            company["avg_burial"],
            "max":              company["max_burial"],
            "sector_mean":      ss.get("avg_burial", {}).get("mean"),
            "sector_median":    ss.get("avg_burial", {}).get("median"),
            "sector_percentile": peer_pct("avg_burial"),
            "outlier_flag":     outlier("avg_burial"),
        },
        "attention_gap": {
            "value":            company["avg_gap"],
            "max":              company["max_gap"],
            "sector_mean":      ss.get("avg_gap", {}).get("mean"),
            "sector_median":    ss.get("avg_gap", {}).get("median"),
            "sector_percentile": peer_pct("avg_gap"),
            "outlier_flag":     outlier("avg_gap"),
        },
        "high_alert_count":   company["high_alert_count"],
        "peers": [
            {
                "ticker":           p["ticker"],
                "avg_materiality":  p["avg_materiality"],
                "avg_burial":       p["avg_burial"],
                "avg_gap":          p["avg_gap"],
            }
            for p in sorted(peers, key=lambda x: x["avg_materiality"] or 0, reverse=True)
        ],
    }


def sector_leaderboard(
    conn: sqlite3.Connection,
    sector: Optional[str] = None,
    metric: str = "avg_materiality",
    top_n: int = 10,
) -> list[dict]:
    """
    Return top_n companies ranked by metric within a sector (or all sectors).
    """
    companies = load_company_stats(conn)
    if sector:
        companies = [c for c in companies if c.get("sector") == sector]
    companies.sort(key=lambda c: c.get(metric) or 0, reverse=True)
    return companies[:top_n]


def top_buried_companies(conn: sqlite3.Connection, top_n: int = 10) -> list[dict]:
    """
    Companies with the highest avg burial scores — most likely to hide disclosures.
    """
    return sector_leaderboard(conn, metric="avg_burial", top_n=top_n)


def cross_sector_table(conn: sqlite3.Connection) -> list[dict]:
    """
    Returns one row per sector with aggregate stats.
    """
    companies  = load_company_stats(conn)
    ss         = build_sector_stats(companies)
    return [
        {
            "sector": sector,
            **{
                metric: ss[sector].get(metric, {})
                for metric in ("avg_materiality", "avg_burial", "avg_gap")
            },
        }
        for sector in sorted(ss.keys())
    ]


def print_comparison(result: dict) -> None:
    if "error" in result:
        print(f"⚠ {result['ticker']}: {result['error']}")
        return

    print(f"\n{'═'*60}")
    print(f"  PEER COMPARISON — {result['ticker']} vs {result['sector']}")
    print(f"  ({result['sector_peer_count']} sector peers, {result['n_alerts']} alerts)")
    print(f"{'═'*60}")

    def row(label, m):
        val  = m.get("value", "—")
        mean = m.get("sector_mean", "—")
        pct  = m.get("sector_percentile", "—")
        flag = m.get("outlier_flag", "")
        flag_str = f"  ⚠ {flag}" if "OUTLIER" in (flag or "") else ""
        print(f"  {label:<20} {str(val):<8} sector_mean={mean:<8} pct={pct}%{flag_str}")

    row("Materiality",   result["materiality"])
    row("Burial Score",  result["burial"])
    row("Attention Gap", result["attention_gap"])
    print(f"\n  CRITICAL/HIGH alerts: {result['high_alert_count']}")

    print(f"\n  Sector peers (ranked by materiality):")
    for p in result["peers"][:5]:
        marker = " ◄ YOU" if p["ticker"] == result["ticker"] else ""
        print(f"    {p['ticker']:<6} mat={p['avg_materiality'] or '—':<7} "
              f"bur={p['avg_burial'] or '—':<7} gap={p['avg_gap'] or '—'}{marker}")
    print(f"{'═'*60}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="EDGAR peer comparison")
    parser.add_argument("--ticker",      help="Single ticker comparison")
    parser.add_argument("--sector",      help="Sector leaderboard")
    parser.add_argument("--all",         action="store_true", help="Cross-sector table")
    parser.add_argument("--top-buried",  action="store_true", help="Most buried companies")
    parser.add_argument("--export",      help="Save JSON to path")
    args = parser.parse_args()

    from database import get_connection, init_db
    conn = get_connection()
    init_db(conn)

    import pathlib

    if args.ticker:
        result = compare_ticker(conn, args.ticker)
        print_comparison(result)
        if args.export:
            pathlib.Path(args.export).write_text(json.dumps(result, indent=2))

    elif args.top_buried:
        results = top_buried_companies(conn)
        print("\nTop 10 companies by avg burial score:")
        for i, c in enumerate(results, 1):
            print(f"  {i:2}. {c['ticker']:<6} {c['name']:<30} burial={c['avg_burial']}")
        if args.export:
            pathlib.Path(args.export).write_text(json.dumps(results, indent=2))

    elif args.all:
        table = cross_sector_table(conn)
        print("\nCross-sector comparison:")
        for row in table:
            mat = row["avg_materiality"].get("mean", "—")
            bur = row["avg_burial"].get("mean", "—")
            n   = row["avg_materiality"].get("n", 0)
            print(f"  {row['sector']:<20} n={n}  mat={mat}  bur={bur}")
        if args.export:
            pathlib.Path(args.export).write_text(json.dumps(table, indent=2))

    elif args.sector:
        leaders = sector_leaderboard(conn, sector=args.sector)
        print(f"\n{args.sector} — ranked by avg materiality:")
        for i, c in enumerate(leaders, 1):
            print(f"  {i:2}. {c['ticker']:<6} mat={c['avg_materiality']} bur={c['avg_burial']} gap={c['avg_gap']}")
        if args.export:
            pathlib.Path(args.export).write_text(json.dumps(leaders, indent=2))

    else:
        parser.print_help()

    conn.close()
