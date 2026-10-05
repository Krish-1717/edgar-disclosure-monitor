"""
filing_pipeline.py — End-to-end orchestrator: fetch → parse → diff → alert.

Provides:
    run_filing_comparison(ticker, form_type, use_news) -> dict
    run_batch(tickers, form_type) -> list[dict]

CLI:
    python filing_pipeline.py --ticker NVDA AAPL MSFT --form 10-K --output data/results/
"""
from __future__ import annotations

import argparse
import json
import logging
import pathlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from filing_fetcher import FilingFetcher, FilingMeta
from filing_parser import parse_filing, ParsedFiling
from filing_differ import diff_filings
from filing_report import generate_alert_payload

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def _safe_parse(meta: FilingMeta) -> ParsedFiling:
    """Parse with error logging."""
    try:
        return parse_filing(meta)
    except Exception as exc:
        log.error("Parse failed for %s %s: %s", meta.ticker, meta.filed_date, exc)
        raise


def run_filing_comparison(
    ticker: str,
    form_type: str = "10-K",
    use_news: bool = True,
) -> dict:
    """
    Full pipeline for one ticker:
    1. Fetch 2 most recent filings
    2. Parse both in parallel
    3. Diff them
    4. Optionally enrich with news signal (4-tuple from news_fetcher v2)
    5. Return alert payload dict

    Returns alert payload matching frontend ALERTS schema.
    """
    ticker = ticker.upper()
    log.info("Starting comparison: %s %s", ticker, form_type)

    # Step 1: fetch metadata
    fetcher = FilingFetcher()
    old_meta, new_meta = fetcher.get_two_most_recent(ticker, form_type)
    log.info("  Old: %s  New: %s", old_meta.filed_date, new_meta.filed_date)

    # Step 2: parse both in parallel
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_old = pool.submit(_safe_parse, old_meta)
        fut_new = pool.submit(_safe_parse, new_meta)
        old_parsed = fut_old.result()
        new_parsed = fut_new.result()

    # Step 3: diff
    diff = diff_filings(old_parsed, new_parsed)
    log.info("  Overall materiality: %.3f  top items: %s",
             diff.overall_materiality, diff.top_changed_items)

    # Step 4: news enrichment (optional)
    composite = 0.5
    direction = "NEUTRAL"
    bucket = "neutral"
    article_count = 0

    if use_news:
        try:
            from news_fetcher import get_coverage_score
            # news_fetcher v2 returns 4-tuple: (composite_score, article_count, sentiment_direction, top_bucket)
            composite, article_count, direction, bucket = get_coverage_score(
                ticker, ticker, new_meta.filed_date
            )
            log.info("  News: composite=%.3f articles=%d direction=%s bucket=%s",
                     composite, article_count, direction, bucket)
        except ImportError:
            log.warning("news_fetcher not available, using defaults")
        except Exception as exc:
            log.warning("News enrichment failed: %s", exc)

    # Step 5: compute attention gap and generate alert
    mat_pct = diff.overall_materiality * 100
    attention_gap = min(100.0, mat_pct / max(composite, 0.01))
    log.info("  Attention gap: %.1f", attention_gap)

    payload = generate_alert_payload(diff, composite, direction, bucket)
    payload["article_count"] = article_count
    payload["attention_gap"] = round(attention_gap, 1)

    return payload


def run_batch(
    tickers: list[str],
    form_type: str = "10-K",
    use_news: bool = True,
    max_workers: int = 4,
) -> list[dict]:
    """
    Run filing comparison for multiple tickers in parallel.
    Returns list of alert payload dicts, skipping failed tickers.
    """
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(run_filing_comparison, t, form_type, use_news): t
            for t in tickers
        }
        for fut in as_completed(futures):
            ticker = futures[fut]
            try:
                payload = fut.result()
                results.append(payload)
                log.info("Completed %s: rank=%s gap=%.1f",
                         ticker, payload.get("rank"), payload.get("gap", 0))
            except Exception as exc:
                log.error("Batch failed for %s: %s", ticker, exc)

    # Sort by attention_gap descending
    results.sort(key=lambda x: x.get("attention_gap", 0), reverse=True)
    return results


# ── CLI ─────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="EDGAR filing comparison pipeline")
    parser.add_argument("--ticker", nargs="+", required=True,
                        help="One or more tickers, e.g. NVDA AAPL MSFT")
    parser.add_argument("--form", default="10-K", help="Form type: 10-K or 10-Q")
    parser.add_argument("--no-news", action="store_true", help="Skip news enrichment")
    parser.add_argument("--output", default="data/results/",
                        help="Directory for JSON output files")
    args = parser.parse_args()

    tickers = [t.upper() for t in args.ticker]
    out_dir = pathlib.Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    if len(tickers) == 1:
        results = [run_filing_comparison(tickers[0], args.form, not args.no_news)]
    else:
        results = run_batch(tickers, args.form, not args.no_news)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tickers_str = "_".join(tickers[:3])
    out_file = out_dir / f"alerts_{tickers_str}_{timestamp}.json"
    out_file.write_text(json.dumps(results, indent=2))

    print(f"\nResults saved to: {out_file}")
    print(f"Total alerts: {len(results)}")
    for r in results:
        print(f"  {r['ticker']:<6} rank={r['rank']:<8} gap={r.get('gap', 0):.1f}  "
              f"materiality={r.get('materiality', 0):.1f}")


if __name__ == "__main__":
    main()
