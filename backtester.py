"""backtester.py — Event study backtester for EDGAR Disclosure Monitor."""
from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

try:
    import yfinance as yf
    _HAS_YF = True
except ImportError:
    _HAS_YF = False


@dataclass
class BacktestResults:
    events_total: int
    events_with_data: int
    mean_car_1d: float
    mean_car_3d: float
    mean_car_5d: float
    mean_car_10d: float
    hit_rate_3d: float          # % of events with positive CAR(0,+3)
    information_coefficient: float  # Spearman rank correlation (score, CAR_3d)
    sharpe_5d: float            # Sharpe of long-only CRITICAL strategy, 5-day hold
    car_by_rank: dict = field(default_factory=dict)


def _spearman_ic(xs: list[float], ys: list[float]) -> float:
    """Spearman rank correlation between two lists."""
    n = len(xs)
    if n < 2:
        return 0.0
    def rank_list(lst):
        sorted_idx = sorted(range(n), key=lambda i: lst[i])
        ranks = [0.0] * n
        for r, i in enumerate(sorted_idx):
            ranks[i] = r + 1
        return ranks
    rx = rank_list(xs)
    ry = rank_list(ys)
    d_sq = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return 1.0 - 6 * d_sq / (n * (n * n - 1))


class EDGARBacktester:
    """
    Event study methodology:
    - Event date = filing date (t=0)
    - Estimation window: t=-120 to t=-11 (normal return estimation)
    - Event window: t=-1, 0, +1, +2, +3, +5, +10
    - Normal return: market model vs SPY
    - Abnormal return: actual - predicted (beta * SPY_return + alpha)
    - CAR: cumulative abnormal return over window
    """

    def __init__(self, start_date: str = "2023-01-01", end_date: str = "2024-12-31"):
        self.start_date = start_date
        self.end_date = end_date
        self.benchmark = "SPY"

    def _fetch_returns(self, ticker: str, start: date, end: date) -> Optional[dict[date, float]]:
        """Fetch daily returns dict using yfinance (returns None if unavailable)."""
        if not _HAS_YF:
            return None
        try:
            td = yf.download(ticker, start=str(start), end=str(end), progress=False, auto_adjust=True)
            if td.empty:
                return None
            closes = td["Close"]
            rets = {}
            prev = None
            for dt_idx, price in closes.items():
                dt = dt_idx.date() if hasattr(dt_idx, "date") else dt_idx
                if prev is not None:
                    rets[dt] = float(price) / float(prev) - 1.0
                prev = price
            return rets
        except Exception:
            return None

    def compute_car(
        self,
        ticker: str,
        event_date: date,
        window: tuple[int, int] = (0, 3),
    ) -> Optional[float]:
        """
        Compute cumulative abnormal return over window (days relative to event).
        Returns None if insufficient data.
        """
        estimation_start = event_date - timedelta(days=170)
        estimation_end = event_date - timedelta(days=10)
        event_end = event_date + timedelta(days=window[1] + 5)

        ticker_rets = self._fetch_returns(ticker, estimation_start, event_end)
        bench_rets = self._fetch_returns(self.benchmark, estimation_start, event_end)

        if ticker_rets is None or bench_rets is None:
            return None

        # Estimate market model in estimation window
        common_est = [
            d for d in ticker_rets
            if estimation_start <= d <= estimation_end and d in bench_rets
        ]
        if len(common_est) < 20:
            return None
        t_est = [ticker_rets[d] for d in common_est]
        b_est = [bench_rets[d] for d in common_est]
        mean_t = sum(t_est) / len(t_est)
        mean_b = sum(b_est) / len(b_est)
        cov = sum((t_est[i] - mean_t) * (b_est[i] - mean_b) for i in range(len(t_est)))
        var_b = sum((b_est[i] - mean_b) ** 2 for i in range(len(b_est)))
        beta = cov / var_b if var_b > 1e-10 else 1.0
        alpha = mean_t - beta * mean_b

        # Compute CAR in event window
        trading_days = sorted(d for d in ticker_rets if d >= event_date)
        car = 0.0
        count = 0
        target = window[1] - window[0] + 1
        for d in trading_days[:target + 10]:
            if count >= target:
                break
            if d in bench_rets:
                abnormal = ticker_rets[d] - (alpha + beta * bench_rets[d])
                car += abnormal
                count += 1
        return car if count > 0 else None

    def run_event_study(self, events: list[dict]) -> BacktestResults:
        """
        Run event study on list of events.
        events: [{ticker, date (str YYYY-MM-DD), score (float), rank (str)}]
        """
        cars_1d, cars_3d, cars_5d, cars_10d = [], [], [], []
        scores_with_car = []
        critical_returns = []
        car_by_rank: dict[str, list[float]] = {}

        for ev in events:
            ticker = ev["ticker"]
            ev_date = date.fromisoformat(ev["date"]) if isinstance(ev["date"], str) else ev["date"]
            score = float(ev.get("score", 50))
            rank = ev.get("rank", "MEDIUM")

            car3 = self.compute_car(ticker, ev_date, window=(0, 3))
            if car3 is None:
                continue

            car1 = self.compute_car(ticker, ev_date, window=(0, 1)) or car3
            car5 = self.compute_car(ticker, ev_date, window=(0, 5)) or car3
            car10 = self.compute_car(ticker, ev_date, window=(0, 10)) or car3

            cars_1d.append(car1)
            cars_3d.append(car3)
            cars_5d.append(car5)
            cars_10d.append(car10)
            scores_with_car.append((score, car3))
            car_by_rank.setdefault(rank, []).append(car3)

            if rank == "CRITICAL":
                critical_returns.append(car5)

        n = len(cars_3d)
        if n == 0:
            return BacktestResults(
                events_total=len(events), events_with_data=0,
                mean_car_1d=0.0, mean_car_3d=0.0, mean_car_5d=0.0, mean_car_10d=0.0,
                hit_rate_3d=0.0, information_coefficient=0.0, sharpe_5d=0.0,
            )

        mean = lambda xs: sum(xs) / len(xs) if xs else 0.0
        std = lambda xs: math.sqrt(sum((x - mean(xs))**2 for x in xs) / len(xs)) if len(xs) > 1 else 1e-10

        hit_rate = sum(1 for c in cars_3d if c > 0) / n
        ic = _spearman_ic([s for s, _ in scores_with_car], [c for _, c in scores_with_car])

        crit_mean = mean(critical_returns)
        crit_std = std(critical_returns)
        sharpe = (crit_mean / crit_std) * math.sqrt(252 / 5) if crit_std > 1e-10 else 0.0

        return BacktestResults(
            events_total=len(events),
            events_with_data=n,
            mean_car_1d=round(mean(cars_1d), 4),
            mean_car_3d=round(mean(cars_3d), 4),
            mean_car_5d=round(mean(cars_5d), 4),
            mean_car_10d=round(mean(cars_10d), 4),
            hit_rate_3d=round(hit_rate, 3),
            information_coefficient=round(ic, 4),
            sharpe_5d=round(sharpe, 3),
            car_by_rank={k: round(mean(v), 4) for k, v in car_by_rank.items()},
        )

    def generate_report(self, results: BacktestResults) -> str:
        lines = [
            "=" * 60,
            "EDGAR Backtest Report",
            "=" * 60,
            f"Events total:          {results.events_total}",
            f"Events with data:      {results.events_with_data}",
            f"Mean CAR(0,+1):        {results.mean_car_1d:+.2%}",
            f"Mean CAR(0,+3):        {results.mean_car_3d:+.2%}",
            f"Mean CAR(0,+5):        {results.mean_car_5d:+.2%}",
            f"Mean CAR(0,+10):       {results.mean_car_10d:+.2%}",
            f"Hit Rate (CAR3d > 0):  {results.hit_rate_3d:.1%}",
            f"Information Coef (IC): {results.information_coefficient:.4f}",
            f"Sharpe (CRITICAL,5d):  {results.sharpe_5d:.3f}",
            "\nCAR by rank:",
        ]
        for rank in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            v = results.car_by_rank.get(rank)
            if v is not None:
                lines.append(f"  {rank:8s}: {v:+.2%}")
        return "\n".join(lines)


def _synthetic_events(n: int = 10, seed: int = 42) -> list[dict]:
    """Generate synthetic events for unit testing without network."""
    rng = random.Random(seed)
    tickers = ["NVDA", "AAPL", "TSLA", "META", "MSFT", "AMZN", "GOOGL", "NFLX", "AMD", "ORCL"]
    ranks = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    events = []
    base_date = date(2024, 1, 15)
    for i in range(n):
        events.append({
            "ticker": tickers[i % len(tickers)],
            "date": (base_date + timedelta(days=i * 7)).isoformat(),
            "score": rng.uniform(20, 95),
            "rank": ranks[i % len(ranks)],
        })
    return events


if __name__ == "__main__":
    bt = EDGARBacktester()
    synthetic = _synthetic_events(10)
    print("Synthetic events (unit test, no network):")
    for ev in synthetic:
        print(f"  {ev['ticker']:6s} {ev['date']}  score={ev['score']:.1f}  [{ev['rank']}]")

    if _HAS_YF:
        print("\nRunning event study with yfinance...")
        results = bt.run_event_study(synthetic)
        print(bt.generate_report(results))
    else:
        print("\nyfinance not installed — skipping live event study.")
        print("Install with: pip install yfinance")"""
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
