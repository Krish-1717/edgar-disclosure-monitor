"""
backtester.py — Attention Gap Signal Backtester

Tests whether the Attention Gap score has predictive power for
future abnormal stock returns. This validates the core hypothesis:
  "High-materiality changes with low press coverage → missed by market → future return"

Methodology (simplified event study):
  1. For each alert with a known attention_gap and filing date:
     - Compute abnormal return over [+1, +21] trading days post-filing
     - Group alerts into HIGH_GAP (top tercile) and LOW_GAP (bottom tercile)
  2. Compare average abnormal returns between groups
  3. Compute Information Coefficient (IC) = Spearman rank correlation
     between attention_gap and forward_return
  4. Report hit rate, mean return, Sharpe-like ratio

Requires financial_metrics.py to have already enriched the alerts table.

Usage:
    python backtester.py                    # backtest all alerts
    python backtester.py --ticker AAPL      # one company
    python backtester.py --min-rank 4       # only HIGH/CRITICAL
    python backtester.py --plot             # save return chart (requires matplotlib)
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

FORWARD_DAYS = 21   # ~1 calendar month of trading days
MIN_ALERTS   = 5    # minimum alerts needed for meaningful stats


# ── Data loading ───────────────────────────────────────────────────────────────

def load_backtest_data(
    conn: sqlite3.Connection,
    ticker: Optional[str] = None,
    min_rank: int = 1,
) -> list[dict]:
    """
    Load alerts enriched with financial metrics.
    Returns list of dicts with attention_gap, materiality_score,
    burial_score, ranking, abnormal_return, filed, ticker.
    """
    query = """
        SELECT a.id, a.ticker, a.filed, a.ranking,
               a.materiality_score, a.burial_score, a.attention_gap,
               a.abnormal_return, a.event_window_return,
               a.filing_day_return, a.volume_ratio, a.price_impact_score,
               a.summary_items
        FROM alerts a
        WHERE a.ranking >= ?
          AND a.abnormal_return IS NOT NULL
    """
    params: list = [min_rank]
    if ticker:
        query += " AND a.ticker = ?"
        params.append(ticker.upper())
    query += " ORDER BY a.filed"

    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ── Signal statistics ──────────────────────────────────────────────────────────

def _spearman_ic(xs: list[float], ys: list[float]) -> float:
    """Spearman rank correlation (Information Coefficient) between xs and ys."""
    if len(xs) < 3:
        return float("nan")
    n = len(xs)

    def rank(lst: list[float]) -> list[float]:
        sorted_vals = sorted(enumerate(lst), key=lambda x: x[1])
        ranks = [0.0] * n
        for r, (i, _) in enumerate(sorted_vals):
            ranks[i] = r + 1
        return ranks

    rx, ry = rank(xs), rank(ys)
    mean_rx = sum(rx) / n
    mean_ry = sum(ry) / n
    num = sum((rx[i] - mean_rx) * (ry[i] - mean_ry) for i in range(n))
    den = math.sqrt(
        sum((rx[i] - mean_rx) ** 2 for i in range(n)) *
        sum((ry[i] - mean_ry) ** 2 for i in range(n))
    )
    return num / den if den else float("nan")


def _sharpe(returns: list[float]) -> float:
    if len(returns) < 2:
        return float("nan")
    mu  = statistics.mean(returns)
    std = statistics.stdev(returns)
    return mu / std if std else float("nan")


def _hit_rate(returns: list[float]) -> float:
    if not returns:
        return float("nan")
    return sum(1 for r in returns if r > 0) / len(returns)


def run_backtest(
    conn: sqlite3.Connection,
    ticker: Optional[str] = None,
    min_rank: int = 1,
    gap_tercile_split: float = 0.33,
) -> dict:
    """
    Run the full backtest. Returns a results dict with statistics.

    Parameters
    ----------
    conn              : open DB connection
    ticker            : limit to one company (None = all)
    min_rank          : minimum alert rank to include
    gap_tercile_split : fraction for HIGH vs LOW gap split (default = top/bottom 33%)
    """
    data = load_backtest_data(conn, ticker=ticker, min_rank=min_rank)

    if len(data) < MIN_ALERTS:
        return {
            "error":   f"Not enough data (need ≥ {MIN_ALERTS} alerts with financial metrics, got {len(data)})",
            "n_alerts": len(data),
        }

    gaps    = [d["attention_gap"]    for d in data]
    returns = [d["abnormal_return"]  for d in data]

    # IC: does attention_gap predict forward abnormal return?
    ic = _spearman_ic(gaps, returns)

    # Tercile split
    sorted_gaps  = sorted(gaps)
    low_thresh   = sorted_gaps[int(len(sorted_gaps) * gap_tercile_split)]
    high_thresh  = sorted_gaps[int(len(sorted_gaps) * (1 - gap_tercile_split))]

    high_gap_rets = [d["abnormal_return"] for d in data if d["attention_gap"] >= high_thresh]
    low_gap_rets  = [d["abnormal_return"] for d in data if d["attention_gap"] <= low_thresh]
    all_rets      = returns

    # Filing-day return analysis
    filing_day_rets = [d["filing_day_return"] for d in data if d.get("filing_day_return") is not None]

    # By rank
    by_rank: dict[int, list[float]] = {}
    for d in data:
        by_rank.setdefault(d["ranking"], []).append(d["abnormal_return"])

    rank_stats = {
        rank: {
            "n": len(rets),
            "mean_return": round(statistics.mean(rets), 5) if rets else None,
            "hit_rate":    round(_hit_rate(rets), 3)       if rets else None,
        }
        for rank, rets in sorted(by_rank.items(), reverse=True)
    }

    results = {
        "n_alerts":            len(data),
        "date_range":          f"{data[0]['filed']} → {data[-1]['filed']}",
        "tickers":             len(set(d["ticker"] for d in data)),

        # Signal quality
        "information_coefficient": round(ic, 4) if not math.isnan(ic) else None,
        "ic_interpretation":   (
            "Strong positive predictive signal" if ic > 0.15 else
            "Moderate signal"                   if ic > 0.05 else
            "Weak signal"                       if ic > 0    else
            "No predictive power"
        ) if not math.isnan(ic) else "Insufficient data",

        # HIGH gap alerts (top tercile)
        "high_gap": {
            "n":           len(high_gap_rets),
            "mean_return": round(statistics.mean(high_gap_rets), 5) if high_gap_rets else None,
            "hit_rate":    round(_hit_rate(high_gap_rets), 3)       if high_gap_rets else None,
            "sharpe":      round(_sharpe(high_gap_rets), 3)         if len(high_gap_rets) >= 2 else None,
        },

        # LOW gap alerts (bottom tercile)
        "low_gap": {
            "n":           len(low_gap_rets),
            "mean_return": round(statistics.mean(low_gap_rets), 5) if low_gap_rets else None,
            "hit_rate":    round(_hit_rate(low_gap_rets), 3)       if low_gap_rets else None,
            "sharpe":      round(_sharpe(low_gap_rets), 3)         if len(low_gap_rets) >= 2 else None,
        },

        # All alerts
        "all": {
            "mean_return":     round(statistics.mean(all_rets), 5),
            "median_return":   round(statistics.median(all_rets), 5),
            "stdev_return":    round(statistics.stdev(all_rets), 5) if len(all_rets) >= 2 else None,
            "hit_rate":        round(_hit_rate(all_rets), 3),
        },

        # Filing-day reaction
        "filing_day": {
            "n":          len(filing_day_rets),
            "mean":       round(statistics.mean(filing_day_rets), 5)  if filing_day_rets else None,
            "hit_rate":   round(_hit_rate(filing_day_rets), 3)        if filing_day_rets else None,
        },

        # By rank
        "by_rank": rank_stats,
    }

    return results


def print_report(results: dict) -> None:
    """Pretty-print backtest results to stdout."""
    if "error" in results:
        print(f"⚠ Backtest skipped: {results['error']}")
        return

    print("\n" + "═" * 60)
    print("  EDGAR DISCLOSURE MONITOR — BACKTEST RESULTS")
    print("═" * 60)
    print(f"  Alerts:       {results['n_alerts']}  ({results['date_range']})")
    print(f"  Tickers:      {results['tickers']}")
    print(f"  Fwd window:   {FORWARD_DAYS} trading days")
    print()

    ic = results.get("information_coefficient")
    print(f"  📐 Information Coefficient (IC): {ic if ic is not None else 'N/A'}")
    print(f"     → {results['ic_interpretation']}")
    print()

    hg = results["high_gap"]
    lg = results["low_gap"]
    print("  📊 HIGH Attention Gap (top tercile):")
    print(f"     n={hg['n']}  mean={hg['mean_return']}  hit_rate={hg['hit_rate']}  sharpe={hg['sharpe']}")
    print("  📉 LOW Attention Gap (bottom tercile):")
    print(f"     n={lg['n']}  mean={lg['mean_return']}  hit_rate={lg['hit_rate']}  sharpe={lg['sharpe']}")

    if hg["mean_return"] is not None and lg["mean_return"] is not None:
        spread = round(hg["mean_return"] - lg["mean_return"], 5)
        print(f"\n  📈 Long-Short Spread: {spread:+.5f} ({spread*100:+.3f}%)")

    print()
    print("  By Rank:")
    for rank, s in results.get("by_rank", {}).items():
        from change_scorer import RANK_LABELS
        label = RANK_LABELS.get(rank, str(rank))
        print(f"    {label:<10} n={s['n']}  mean={s['mean_return']}  hit_rate={s['hit_rate']}")

    print("═" * 60 + "\n")


def save_backtest_results(results: dict, path: pathlib.Path) -> None:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2))
    log.info("Backtest results saved to %s", path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Backtest the EDGAR Attention Gap signal")
    parser.add_argument("--ticker",   help="Limit to one ticker")
    parser.add_argument("--min-rank", type=int, default=1)
    parser.add_argument("--output",   help="Save results JSON to this path")
    args = parser.parse_args()

    from database import get_connection, init_db
    conn = get_connection()
    init_db(conn)

    results = run_backtest(conn, ticker=args.ticker, min_rank=args.min_rank)
    print_report(results)

    if args.output:
        save_backtest_results(results, pathlib.Path(args.output))

    conn.close()
