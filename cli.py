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
    main()"""
cli.py — Unified Command-Line Interface for EDGAR Disclosure Monitor

A clean, rich CLI (built with Click) that wraps every operation:
  pipeline, alerts, watchlist, trends, sector comparison, backtest,
  export, email, RSS watcher, and scheduler.

Install:
    pip install click rich

Run:
    python cli.py --help
    python cli.py pipeline run --ticker AAPL
    python cli.py alerts list --min-rank 4
    python cli.py trends show --ticker NVDA
    python cli.py compare --ticker JPM
    python cli.py backtest
    python cli.py export alerts --output data/exports/
    python cli.py watch --interval 15
    python cli.py schedule start
"""
from __future__ import annotations
import json
import logging
import pathlib
import sys

try:
    import click
except ImportError:
    print("Click not installed. Run: pip install click")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.table import Table
    from rich import box
    RICH = True
    console = Console()
except ImportError:
    RICH = False
    console = None  # type: ignore

logging.basicConfig(level=logging.WARNING,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

RANK_COLORS_RICH = {5: "red",  4: "yellow", 3: "bright_yellow", 2: "cyan", 1: "white"}
RANK_LABELS      = {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "MINIMAL"}


def _db():
    from database import get_connection, init_db
    conn = get_connection()
    init_db(conn)
    return conn


def _echo(msg: str, style: str = "") -> None:
    if RICH:
        console.print(msg, style=style)
    else:
        click.echo(msg)


# ── Root ───────────────────────────────────────────────────────────────────────

@click.group()
@click.version_option("1.0.0", prog_name="edgar-monitor")
def cli():
    """📋 EDGAR Disclosure Monitor — detect what companies try to hide."""
    pass


# ── Pipeline ───────────────────────────────────────────────────────────────────

@cli.group()
def pipeline():
    """Run the ingestion pipeline."""
    pass


@pipeline.command("run")
@click.option("--ticker",  "-t", help="Single ticker (default: full watchlist)")
@click.option("--tickers", "-T", multiple=True, help="Multiple tickers")
@click.option("--all",     "-a", is_flag=True, help="Full watchlist")
@click.option("--verbose", "-v", is_flag=True)
def pipeline_run(ticker, tickers, all, verbose):
    """Ingest filings and compute alerts."""
    if verbose:
        logging.getLogger().setLevel(logging.INFO)

    from run_pipeline import run
    from watchlist import WATCHLIST

    if ticker:
        targets = [ticker.upper()]
    elif tickers:
        targets = [t.upper() for t in tickers]
    else:
        targets = [w["ticker"] for w in WATCHLIST]

    _echo(f"Running pipeline for: {', '.join(targets[:5])}{'...' if len(targets)>5 else ''}", "bold")
    run(targets)
    _echo("✓ Pipeline complete", "green")


@pipeline.command("status")
def pipeline_status():
    """Show DB stats for the current pipeline state."""
    conn = _db()
    n_co     = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    n_fil    = conn.execute("SELECT COUNT(*) FROM filings WHERE fetched=1").fetchone()[0]
    n_alerts = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    n_hi     = conn.execute("SELECT COUNT(*) FROM alerts WHERE ranking >= 4").fetchone()[0]
    conn.close()

    if RICH:
        t = Table(box=box.ROUNDED, show_header=False)
        t.add_row("Companies",     str(n_co))
        t.add_row("Filings fetched", str(n_fil))
        t.add_row("Total alerts",  str(n_alerts))
        t.add_row("High/Critical", f"[red]{n_hi}[/red]")
        console.print(t)
    else:
        click.echo(f"Companies: {n_co}  Filings: {n_fil}  Alerts: {n_alerts}  High+: {n_hi}")


# ── Alerts ─────────────────────────────────────────────────────────────────────

@cli.group()
def alerts():
    """Browse and filter alerts."""
    pass


@alerts.command("list")
@click.option("--ticker",   "-t", help="Filter by ticker")
@click.option("--min-rank", "-r", default=3, type=int, help="Min rank (1-5)")
@click.option("--limit",    "-n", default=20, type=int)
@click.option("--json",     "as_json", is_flag=True, help="Output as JSON")
def alerts_list(ticker, min_rank, limit, as_json):
    """List top alerts ranked by Attention Gap."""
    conn = _db()
    query = """
        SELECT a.ticker, f.form, a.filed, a.ranking,
               a.materiality_score, a.burial_score, a.attention_gap, a.summary_items
        FROM alerts a JOIN filings f ON a.new_filing_id = f.id
        WHERE a.ranking >= ?
    """
    params = [min_rank]
    if ticker:
        query += " AND a.ticker = ?"
        params.append(ticker.upper())
    query += " ORDER BY a.attention_gap DESC LIMIT ?"
    params.append(limit)
    rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    conn.close()

    if as_json:
        click.echo(json.dumps(rows, indent=2))
        return

    if not rows:
        _echo("No alerts found.", "yellow")
        return

    if RICH:
        t = Table(title=f"Top Alerts (rank ≥ {RANK_LABELS.get(min_rank, min_rank)})",
                  box=box.ROUNDED, show_lines=False)
        t.add_column("Ticker", style="bold")
        t.add_column("Form")
        t.add_column("Filed")
        t.add_column("Rank")
        t.add_column("Materiality", justify="right")
        t.add_column("Burial",      justify="right")
        t.add_column("Gap ↑",       justify="right", style="cyan")
        for r in rows:
            rk    = r["ranking"]
            color = RANK_COLORS_RICH.get(rk, "white")
            t.add_row(
                r["ticker"], r["form"] or "—", r["filed"],
                f"[{color}]{RANK_LABELS.get(rk,'—')}[/{color}]",
                f"{r['materiality_score']:.1f}",
                f"{r['burial_score']:.1f}",
                f"{r['attention_gap']:.1f}",
            )
        console.print(t)
    else:
        for r in rows:
            click.echo(
                f"{r['ticker']:<6} {r['form'] or '?':<6} {r['filed']:<12} "
                f"rank={r['ranking']} mat={r['materiality_score']:.1f} gap={r['attention_gap']:.1f}"
            )


# ── Watchlist ──────────────────────────────────────────────────────────────────

@cli.group()
def watchlist():
    """Manage the company watchlist."""
    pass


@watchlist.command("show")
def watchlist_show():
    """Display all watched companies."""
    conn = _db()
    rows = conn.execute("""
        SELECT c.ticker, c.name, c.sector,
               COUNT(DISTINCT f.id) AS filings, COUNT(DISTINCT a.id) AS alerts
        FROM companies c
        LEFT JOIN filings f ON f.ticker = c.ticker AND f.fetched=1
        LEFT JOIN alerts  a ON a.ticker = c.ticker
        GROUP BY c.ticker ORDER BY c.sector, c.ticker
    """).fetchall()
    conn.close()

    if RICH:
        t = Table(title="Watchlist", box=box.ROUNDED)
        t.add_column("Ticker"); t.add_column("Company"); t.add_column("Sector")
        t.add_column("Filings", justify="right"); t.add_column("Alerts", justify="right")
        for r in rows:
            t.add_row(r["ticker"], r["name"], r["sector"], str(r["filings"]), str(r["alerts"]))
        console.print(t)
    else:
        for r in rows:
            click.echo(f"{r['ticker']:<6} {r['sector']:<15} filings={r['filings']} alerts={r['alerts']}")


@watchlist.command("add")
@click.argument("ticker")
@click.option("--name",   default="", help="Company name")
@click.option("--sector", default="Unknown", help="Sector")
def watchlist_add(ticker, name, sector):
    """Add a ticker to the watchlist."""
    from database import get_connection, init_db, upsert_company, transaction
    conn = get_connection()
    init_db(conn)
    from edgar_client import EdgarClient
    import os
    ua = os.getenv("EDGAR_USER_AGENT", "Krish Patel patelkrish1717@gmail.com")
    try:
        client = EdgarClient(ua)
        cik = client.ticker_to_cik(ticker.upper())
    except Exception:
        cik = ""
    with transaction(conn):
        upsert_company(conn, ticker.upper(), name or ticker.upper(), sector, cik)
    conn.close()
    _echo(f"✓ Added {ticker.upper()} ({sector}) to watchlist", "green")


# ── Trends ─────────────────────────────────────────────────────────────────────

@cli.group()
def trends():
    """Analyze disclosure trends over time."""
    pass


@trends.command("show")
@click.option("--ticker", "-t", required=True, help="Ticker to analyze")
@click.option("--export", help="Save JSON to path")
def trends_show(ticker, export):
    """Show materiality and burial trends for a company."""
    from trend_analyzer import analyze_ticker, print_ticker_report
    conn = _db()
    result = analyze_ticker(conn, ticker)
    conn.close()
    print_ticker_report(result)
    if export:
        pathlib.Path(export).write_text(json.dumps(result, indent=2))
        _echo(f"Saved to {export}", "dim")


@trends.command("sector")
@click.option("--export", help="Save JSON to path")
def trends_sector(export):
    """Sector-level trend summary."""
    from trend_analyzer import sector_trend_summary
    conn = _db()
    summary = sector_trend_summary(conn)
    conn.close()
    for sector, s in summary.items():
        _echo(f"{sector}: {s['n_companies']} cos  mat={s['mean_materiality']}  "
              f"bur={s['mean_burial']}  rising={s['rising_companies']}")
    if export:
        pathlib.Path(export).write_text(json.dumps(summary, indent=2))


# ── Compare ────────────────────────────────────────────────────────────────────

@cli.command("compare")
@click.option("--ticker",     "-t", help="Single company peer comparison")
@click.option("--top-buried", is_flag=True, help="Most buried companies")
@click.option("--sector",     help="Sector leaderboard")
def compare(ticker, top_buried, sector):
    """Peer comparison against sector benchmarks."""
    from sector_comparator import compare_ticker, print_comparison, top_buried_companies, sector_leaderboard
    conn = _db()
    if ticker:
        result = compare_ticker(conn, ticker)
        print_comparison(result)
    elif top_buried:
        results = top_buried_companies(conn)
        _echo("\nTop companies by avg burial score:")
        for i, c in enumerate(results, 1):
            click.echo(f"  {i:2}. {c['ticker']:<6} {c['name']:<30} burial={c['avg_burial']}")
    elif sector:
        leaders = sector_leaderboard(conn, sector=sector)
        _echo(f"\n{sector} — ranked by materiality:")
        for i, c in enumerate(leaders, 1):
            click.echo(f"  {i:2}. {c['ticker']:<6} mat={c['avg_materiality']}  bur={c['avg_burial']}")
    else:
        _echo("Provide --ticker, --top-buried, or --sector", "yellow")
    conn.close()


# ── Backtest ───────────────────────────────────────────────────────────────────

@cli.command("backtest")
@click.option("--ticker",   "-t", help="Limit to one ticker")
@click.option("--min-rank", "-r", default=1, type=int)
@click.option("--output",   help="Save JSON results to path")
def backtest_cmd(ticker, min_rank, output):
    """Backtest the Attention Gap signal against realized returns."""
    from backtester import run_backtest, print_report, save_backtest_results
    conn = _db()
    results = run_backtest(conn, ticker=ticker, min_rank=min_rank)
    conn.close()
    print_report(results)
    if output:
        save_backtest_results(results, pathlib.Path(output))
        _echo(f"Saved to {output}", "dim")


# ── Export ─────────────────────────────────────────────────────────────────────

@cli.group()
def export():
    """Export data to CSV or PDF."""
    pass


@export.command("alerts")
@click.option("--output",   "-o", default="data/exports/", help="Output directory")
@click.option("--min-rank", "-r", default=1, type=int)
def export_alerts(output, min_rank):
    """Export alerts to CSV."""
    from export_engine import export_alerts_csv
    conn = _db()
    path = export_alerts_csv(conn, pathlib.Path(output) / "alerts.csv", min_rank=min_rank)
    conn.close()
    _echo(f"✓ Exported to {path}", "green")


@export.command("pdf")
@click.option("--alert-id", "-i", required=True, type=int)
@click.option("--output",   "-o", default="data/exports/")
def export_pdf(alert_id, output):
    """Export a single alert as a PDF report."""
    from export_engine import export_alert_pdf
    conn = _db()
    path = export_alert_pdf(conn, alert_id, pathlib.Path(output) / f"alert_{alert_id}.pdf")
    conn.close()
    if path:
        _echo(f"✓ PDF saved to {path}", "green")
    else:
        _echo("Install reportlab: pip install reportlab", "yellow")


# ── Watch ──────────────────────────────────────────────────────────────────────

@cli.command("watch")
@click.option("--interval", "-i", default=15, type=int, help="Poll interval (minutes)")
@click.option("--once",     is_flag=True, help="Check once and exit")
@click.option("--form",     default="both", type=click.Choice(["10-K", "10-Q", "both"]))
@click.option("--no-trigger", is_flag=True, help="Log only, don't run pipeline")
def watch_cmd(interval, once, form, no_trigger):
    """Watch SEC EDGAR RSS for new filings in real time."""
    from sec_rss_watcher import poll
    logging.getLogger().setLevel(logging.INFO)
    forms = ["10-K", "10-Q"] if form == "both" else [form]
    _echo(f"Watching SEC RSS (interval={interval}m, forms={forms})", "bold")
    poll(form_types=forms, interval_min=interval, run_once=once, auto_trigger=not no_trigger)


# ── Schedule ───────────────────────────────────────────────────────────────────

@cli.group()
def schedule():
    """Start or stop the automated scheduler."""
    pass


@schedule.command("start")
@click.option("--once",   is_flag=True, help="Run once immediately and exit")
@click.option("--ticker", "-t", help="Single ticker")
@click.option("--cron",   help="Custom cron expression (e.g. '0 8 * * 1-5')")
def schedule_start(once, ticker, cron):
    """Start the background scheduler (pipeline + enrichment + digest)."""
    from scheduler import start_scheduler, run_once
    logging.getLogger().setLevel(logging.INFO)
    tickers = [ticker.upper()] if ticker else None
    if once:
        run_once(tickers)
    else:
        _echo("Starting scheduler (Ctrl+C to stop)...", "bold")
        start_scheduler(tickers, cron_override=cron)


# ── Email ──────────────────────────────────────────────────────────────────────

@cli.command("email")
@click.option("--to",       help="Recipients (comma-separated)")
@click.option("--min-rank", default=4, type=int)
@click.option("--dry-run",  is_flag=True)
def email_cmd(to, min_rank, dry_run):
    """Send an alert digest email."""
    from alert_emailer import send_digest
    conn = _db()
    recipients = [e.strip() for e in to.split(",")] if to else None
    success = send_digest(conn, recipients=recipients, min_rank=min_rank, dry_run=dry_run)
    conn.close()
    if success:
        _echo("✓ Email sent" if not dry_run else "✓ Dry run complete", "green")
    else:
        _echo("✗ Email failed — check EMAIL_TO / SMTP_USER env vars", "red")


if __name__ == "__main__":
    cli()
