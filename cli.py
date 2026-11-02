"""cli.py — Command-line interface for EDGAR Disclosure Monitor."""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from datetime import datetime


# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------

_USE_COLOR = sys.stdout.isatty()

def _c(text: str, code: str) -> str:
    if not _USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"

def red(t):    return _c(t, "31")
def yellow(t): return _c(t, "33")
def green(t):  return _c(t, "32")
def cyan(t):   return _c(t, "36")
def bold(t):   return _c(t, "1")

_RANK_COLOR = {
    "CRITICAL": red,
    "HIGH": yellow,
    "MEDIUM": cyan,
    "LOW": lambda t: t,
    "NOISE": lambda t: t,
}


def _rank_color(rank: str, text: str) -> str:
    return _RANK_COLOR.get(rank, lambda t: t)(text)


# ---------------------------------------------------------------------------
# Progress bar
# ---------------------------------------------------------------------------

def _progress(current: int, total: int, label: str = "") -> None:
    pct = current / total if total else 0
    bar_len = 30
    filled = int(bar_len * pct)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\r  [{bar}] {current}/{total} {label}   ", end="", flush=True)
    if current == total:
        print()


# ---------------------------------------------------------------------------
# Stub pipeline helpers (real implementations live in other modules)
# ---------------------------------------------------------------------------

def _run_pipeline(tickers: list[str]) -> list[dict]:
    """Run full pipeline for each ticker (stub: generates mock scores)."""
    import math, random
    results = []
    rng = random.Random(42)
    for i, ticker in enumerate(tickers, start=1):
        _progress(i, len(tickers), ticker)
        mat = rng.uniform(0.2, 0.95)
        nq  = rng.uniform(0.1, 0.85)
        cnt = rng.randint(1, 25)
        composite = 0.35 * min(cnt / 20, 1.0) + 0.65 * nq
        gap = mat / max(composite, 0.01)
        base = min(gap * 100, 100)
        bonus = 10.0 if cnt < 5 else 0.0
        penalty = 15.0 if mat < 0.2 else 0.0
        final = max(0.0, min(100.0, base + bonus - penalty))
        rank_map = [(80, "CRITICAL"), (60, "HIGH"), (40, "MEDIUM"), (20, "LOW")]
        rank = next((r for t, r in rank_map if final >= t), "NOISE")
        conf = math.sqrt(min(cnt / 20, 1.0)) * mat
        results.append({
            "ticker": ticker, "materiality_score": round(mat, 4),
            "news_quality_score": round(nq, 4), "final_score": round(final, 2),
            "rank": rank, "confidence": round(conf, 4), "article_count": cnt,
        })
    return results


def _load_alerts(path: str = "data/ranked_alerts.json") -> list[dict]:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f).get("alerts", [])
    return []


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> None:
    print(bold(f"\nRunning EDGAR pipeline for: {', '.join(args.tickers)}\n"))
    results = _run_pipeline(args.tickers)
    print()
    for r in results:
        rank = r["rank"]
        print(
            f"  {r['ticker']:6s} "
            + _rank_color(rank, f"[{rank:8s}]")
            + f"  score={r['final_score']:5.1f}  "
            f"mat={r['materiality_score']:.2f}  "
            f"conf={r['confidence']:.2f}"
        )
    print(f"\n{green('Done.')} {len(results)} tickers processed.")


def cmd_score(args: argparse.Namespace) -> None:
    print(bold(f"\nScoring {args.ticker}..."))
    results = _run_pipeline([args.ticker])
    r = results[0]
    rank = r["rank"]
    print(f"  Ticker:           {r['ticker']}")
    print(f"  Final Score:      {_rank_color(rank, str(r['final_score']))}")
    print(f"  Rank:             {_rank_color(rank, rank)}")
    print(f"  Materiality:      {r['materiality_score']}")
    print(f"  News Quality:     {r['news_quality_score']}")
    print(f"  Article Count:    {r['article_count']}")
    print(f"  Confidence:       {r['confidence']}")


def cmd_watch(args: argparse.Namespace) -> None:
    interval = args.interval
    print(bold(f"\nWatching: {', '.join(args.tickers)}  (interval={interval}s)"))
    print("Press Ctrl+C to stop.\n")
    iteration = 0
    try:
        while True:
            iteration += 1
            ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            print(cyan(f"[{ts}] Iteration #{iteration}"))
            results = _run_pipeline(args.tickers)
            print()
            for r in results:
                rank = r["rank"]
                if rank in ("CRITICAL", "HIGH"):
                    print(
                        f"  {bold('!')} {r['ticker']:6s} "
                        + _rank_color(rank, f"[{rank}]")
                        + f"  score={r['final_score']:.1f}"
                    )
            print(f"\n  Sleeping {interval}s...\n")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nWatch stopped.")

def cmd_backtest(args: argparse.Namespace) -> None:
    print(bold(f"\nBacktesting {', '.join(args.tickers)} from {args.start} to {args.end}"))
    try:
        from backtester import EDGARBacktester, _synthetic_events
        bt = EDGARBacktester(start_date=args.start, end_date=args.end)
        events = _synthetic_events(len(args.tickers) * 5)
        results = bt.run_event_study(events)
        print(bt.generate_report(results))
    except ImportError:
        print(yellow("  backtester.py not found — using synthetic results."))
        print("  IC=0.18  Hit Rate=61%  Sharpe=1.40")


def cmd_alerts(args: argparse.Namespace) -> None:
    alerts = _load_alerts()
    if not alerts:
        print(yellow("No alerts found. Run 'cli.py run TICKER' first."))
        return
    rank_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "NOISE": 0}
    threshold = rank_order.get(args.rank.upper(), 2)
    filtered = [a for a in alerts if rank_order.get(a.get("rank", "NOISE"), 0) >= threshold]
    filtered.sort(key=lambda a: -a.get("final_score", 0))
    top = filtered[: args.top]
    print(bold(f"\nTop {args.top} alerts (rank >= {args.rank}):"))
    for i, a in enumerate(top, start=1):
        rank = a.get("rank", "NOISE")
        print(
            f"  {i:2d}. {a.get('ticker','???'):6s} "
            + _rank_color(rank, f"[{rank:8s}]")
            + f"  score={a.get('final_score',0):.1f}"
        )


def cmd_cache(args: argparse.Namespace) -> None:
    from filing_cache import FilingCache
    cache = FilingCache()
    if args.cache_cmd == "stats":
        stats = cache.cache_stats()
        print(bold("\nCache statistics:"))
        for k, v in stats.items():
            print(f"  {k:20s}: {v}")
    elif args.cache_cmd == "clear":
        removed = cache.evict_old(max_age_days=args.older_than)
        print(green(f"Removed {removed} cache files older than {args.older_than} days."))


def cmd_notify(args: argparse.Namespace) -> None:
    print(bold(f"\nSending test notification for {args.ticker}..."))
    payload = {
        "ticker": args.ticker,
        "rank": "HIGH",
        "final_score": 72.5,
        "materiality_score": 0.85,
        "timestamp": datetime.utcnow().isoformat(),
        "message": f"Test alert for {args.ticker}",
    }
    print(json.dumps(payload, indent=2))
    notif_path = "data/notifications.jsonl"
    os.makedirs("data", exist_ok=True)
    with open(notif_path, "a") as f:
        f.write(json.dumps(payload) + "\n")
    print(green(f"\nNotification written to {notif_path}"))


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cli.py",
        description="EDGAR Disclosure Monitor — CLI",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # run
    r = sub.add_parser("run", help="Full pipeline for tickers")
    r.add_argument("tickers", nargs="+", metavar="TICKER")

    # score
    s = sub.add_parser("score", help="Compute EDGAR score for a single ticker")
    s.add_argument("ticker")

    # watch
    w = sub.add_parser("watch", help="Start continuous monitoring")
    w.add_argument("tickers", nargs="+", metavar="TICKER")
    w.add_argument("--interval", type=int, default=300, metavar="SECONDS")

    # backtest
    bt = sub.add_parser("backtest", help="Run event study backtester")
    bt.add_argument("--tickers", nargs="+", default=["NVDA", "AAPL"])
    bt.add_argument("--start", default="2023-01-01")
    bt.add_argument("--end",   default="2024-12-31")

    # alerts
    al = sub.add_parser("alerts", help="Show ranked alerts")
    al.add_argument("--rank", default="MEDIUM")
    al.add_argument("--top",  type=int, default=10)

    # cache
    ca = sub.add_parser("cache", help="Cache management")
    ca_sub = ca.add_subparsers(dest="cache_cmd", required=True)
    ca_sub.add_parser("stats")
    cl = ca_sub.add_parser("clear")
    cl.add_argument("--older-than", type=int, default=30, dest="older_than")

    # notify
    nt = sub.add_parser("notify", help="Test notification")
    nt.add_argument("action", choices=["test"])
    nt.add_argument("ticker")

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    dispatch = {
        "run": cmd_run,
        "score": cmd_score,
        "watch": cmd_watch,
        "backtest": cmd_backtest,
        "alerts": cmd_alerts,
        "cache": cmd_cache,
        "notify": cmd_notify,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
