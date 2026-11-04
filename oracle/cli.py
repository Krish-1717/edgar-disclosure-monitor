"""Command line: ``python -m oracle crawl NVDA AAPL --forms 10-K,10-Q``."""
from __future__ import annotations

import argparse
import logging
import pathlib
import sys

from . import __version__
from .config import ConfigError, Settings, parse_forms


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m oracle", description="ORACLE SEC EDGAR crawler")
    p.add_argument("--version", action="version", version=f"ORACLE {__version__}")
    p.add_argument("--db", type=pathlib.Path, help="SQLite path (default: ORACLE_DB_PATH or data/oracle/oracle.db)")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("crawl", help="discover + download new filings for tickers")
    c.add_argument("tickers", nargs="+", help="tickers or numeric CIKs")
    c.add_argument("--forms", help="comma list (default: Tier 1: 10-K,10-Q,8-K,DEF 14A,4,S-1,S-4); amendments included")
    c.add_argument("--since", help="only filings on/after YYYY-MM-DD")
    c.add_argument("--limit", type=int, default=10, help="most recent N matching filings per ticker (0 = all; default 10)")
    c.add_argument("--data-dir", type=pathlib.Path, help="document folder (default: ORACLE_DATA_DIR)")
    c.add_argument("--rps", type=float, help="max requests/second (<= 10, default 8)")
    c.add_argument("--refresh", action="store_true", help="re-download filings already fetched")
    c.add_argument("--no-extract", action="store_true", help="skip 10-K/10-Q section segmentation")

    l = sub.add_parser("filings", help="list stored filings for a ticker")
    l.add_argument("ticker")
    l.add_argument("--form")
    l.add_argument("--limit", type=int, default=20)

    e = sub.add_parser("extract", help="re-run 10-K/10-Q section segmentation on stored documents (offline)")
    e.add_argument("ticker", nargs="?")

    x = sub.add_parser("export", help="write static JSON feeds for the GitHub Pages site")
    x.add_argument("tickers", nargs="*", help="default: every crawled company")
    x.add_argument("--out", type=pathlib.Path, default=pathlib.Path("data/oracle/export"),
                   help="output folder (default data/oracle/export, gitignored)")

    s = sub.add_parser("serve", help="run the read API")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    return p


def _cmd_crawl(args, settings: Settings) -> int:
    from .client import SecClient
    from .crawler import Crawler
    from .storage import Store

    forms = parse_forms(args.forms) if args.forms else settings.forms
    store = Store(settings.db_path)
    with SecClient(settings.user_agent, max_rps=args.rps or settings.max_rps) as client:
        crawler = Crawler(client, store, args.data_dir or settings.data_dir, extract_sections=not args.no_extract)
        results = crawler.crawl(args.tickers, forms, since=args.since, limit=args.limit or None,
                                refresh=args.refresh)
        requests = client.request_count

    print(f"forms: {', '.join(forms)}")
    print(f"{'TICKER':<8} {'CIK':>10}  {'MATCHED':>7} {'NEW':>4} {'AMEND':>5} {'DEDUP':>5} {'SECTIONS':>8} {'ERR':>3}  NAME")
    for r in results:
        print(f"{r.ticker:<8} {r.cik or '-':>10}  {r.discovered:>7} {len(r.new):>4} {len(r.amendments):>5} "
              f"{r.deduplicated:>5} {r.sections:>8} {len(r.errors):>3}  {r.name}")
        for e in r.errors[:5]:
            print(f"   ! {e}")
    print(f"{requests} SEC requests; db: {settings.db_path}")
    return 1 if any(r.errors for r in results) else 0


def _cmd_filings(args, settings: Settings) -> int:
    from .storage import Store

    store = Store(settings.db_path)
    company = store.get_company(args.ticker)
    if not company:
        print(f"{args.ticker.upper()} not crawled yet", file=sys.stderr)
        return 1
    rows = store.list_filings(company["cik"], form=args.form, limit=args.limit)
    print(f"{company['ticker']} - {company['name']} (CIK {company['cik']})")
    for r in rows:
        secs = store.sections_for(r["accession"])
        sec_txt = ",".join(s["key"] for s in secs)
        amend = f" v{r['version']} amends {r['amends_accession']}" if r["is_amendment"] else ""
        print(f"  {r['filing_date']}  {r['form']:<8} {r['accession']}  {r['status']:<8}{amend}  {sec_txt}")
    return 0


def _cmd_extract(args, settings: Settings) -> int:
    from .crawler import reextract
    from .storage import Store

    rows = reextract(Store(settings.db_path), args.ticker)
    for acc, form, n in rows:
        print(f"  {form:<6} {acc}  {n} sections")
    print(f"re-segmented {len(rows)} filings")
    return 0


def _cmd_export(args, settings: Settings) -> int:
    from .export import write_export
    from .storage import Store

    manifest = write_export(Store(settings.db_path), args.out, args.tickers or None)
    for c in manifest["companies"]:
        size = (args.out / c["feed"]).stat().st_size
        print(f"  {c['ticker']:<6} {c['filings']:>3} filings  {size / 1024:7.1f} KB  {c['feed']}")
    print(f"wrote {len(manifest['companies'])} feeds + index.json to {args.out}")
    return 0


def _cmd_serve(args, settings: Settings) -> int:
    import uvicorn

    from .api import create_app

    uvicorn.run(create_app(settings.db_path), host=args.host, port=args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.INFO if args.verbose else logging.WARNING)
    try:
        settings = Settings.from_env()
        if args.db:
            settings.db_path = args.db
        handler = {"crawl": _cmd_crawl, "filings": _cmd_filings, "extract": _cmd_extract, "export": _cmd_export,
                   "serve": _cmd_serve}[args.command]
        return handler(args, settings)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
