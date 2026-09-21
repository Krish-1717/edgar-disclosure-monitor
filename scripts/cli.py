"""
scripts/cli.py -- EDGAR Disclosure Monitor command-line interface
Day 10 Commit 2: Fetch, diff, score, and alert on SEC filings.
"""
from __future__ import annotations
import argparse
import json
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from edgar.nlp_scorer import NLPScorer, MaterialityResult


# ââ Demo data (used when --demo flag is set) ââââââââââââââââââââââââââââââââââ

_DEMO_SECTIONS = {
    "AAPL": {
        "risk_factors": (
            "The company faces normal competitive risks in the technology sector. "
            "International sales represent a significant portion of revenue.",
            "The company identified a material weakness in internal controls related "
            "to revenue recognition. An SEC investigation has been initiated. "
            "Going concern uncertainties exist given significant covenant violations.",
        ),
        "mda": (
            "Revenue grew 8% year-over-year driven by iPhone sales. "
            "Operating margin improved to 28%.",
            "Revenue declined 12% year-over-year due to supply chain disruptions. "
            "Operating margin compressed to 22% amid restructuring charges.",
        ),
        "legal_proceedings": (
            "The company is party to certain litigation in the ordinary course of business.",
            "The company faces class action litigation and regulatory action from the DOJ "
            "regarding alleged fraud in financial reporting. Management believes the "
            "aggregate exposure could be material.",
        ),
    }
}


# ââ Formatting helpers ââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def _color(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m"


def _red(t): return _color(t, "91")
def _green(t): return _color(t, "92")
def _yellow(t): return _color(t, "93")
def _bold(t): return _color(t, "1")


def _materiality_bar(score: float, width: int = 30) -> str:
    filled = int(score * width)
    bar = "â" * filled + "â" * (width - filled)
    pct = f"{score:.1%}"
    if score >= 0.5:
        return _red(f"[{bar}] {pct}")
    elif score >= 0.25:
        return _yellow(f"[{bar}] {pct}")
    return _green(f"[{bar}] {pct}")


def _print_result(ticker: str, section: str, result: MaterialityResult,
                  verbose: bool = False):
    flag = _red("â   MATERIAL") if result.is_material() else _green("â  OK      ")
    print(f"  {flag}  {ticker}/{section:<20}  {_materiality_bar(result.materiality)}")
    if verbose:
        print(f"           kw={result.keyword_score:.3f}  "
              f"snt_Î={result.sentiment_delta:.3f}  "
              f"edit={result.structural_change:.3f}")
        if result.keywords_found:
            print(f"           keywords: {', '.join(result.keywords_found[:5])}")


# ââ Commands ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def cmd_score(args):
    scorer = NLPScorer(
        kw_weight=args.kw_weight,
        snt_weight=args.snt_weight,
        edit_weight=args.edit_weight,
    )
    old = Path(args.old).read_text()
    new = Path(args.new).read_text()
    result = scorer.score(old, new)

    if args.json:
        print(json.dumps({
            "materiality": round(result.materiality, 5),
            "is_material": result.is_material(args.threshold),
            "keyword_score": round(result.keyword_score, 5),
            "sentiment_delta": round(result.sentiment_delta, 5),
            "structural_change": round(result.structural_change, 5),
            "keywords_found": result.keywords_found,
        }, indent=2))
    else:
        print(f"\n{_bold('EDGAR Materiality Score')}")
        print(f"  Old: {args.old}")
        print(f"  New: {args.new}")
        print(f"\n  {result.summary()}")
        print(f"  Components:")
        print(f"    Keyword density:   {result.keyword_score:.4f}")
        print(f"    Sentiment delta:   {result.sentiment_delta:.4f}")
        print(f"    Structural change: {result.structural_change:.4f}")
        if result.keywords_found:
            print(f"    Keywords found:    {', '.join(result.keywords_found)}")


def cmd_demo(args):
    scorer = NLPScorer()
    ticker = args.ticker or "AAPL"
    sections = _DEMO_SECTIONS.get(ticker)
    if not sections:
        print(f"No demo data for {ticker}. Available: {', '.join(_DEMO_SECTIONS)}")
        return

    print(f"\n{_bold(f'EDGAR Disclosure Monitor â {ticker}')}")
    print(f"{'â'*65}")

    material_count = 0
    results = scorer.score_sections({k: v for k, v in sections.items()})
    for section, result in results.items():
        _print_result(ticker, section, result, verbose=args.verbose)
        if result.is_material():
            material_count += 1

    print(f"\n  Summary: {material_count}/{len(results)} sections flagged as material")
    if material_count > 0:
        print(_red(f"  â   ACTION REQUIRED: Review flagged sections immediately"))


def cmd_watch(args):
    """Stub for future continuous monitoring mode."""
    print(f"Watching {args.ticker} filings every {args.interval}h â not yet implemented.")
    print("Future: poll EDGAR XBRL API, diff sections, alert on material changes.")


# ââ Main ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def main():
    p = argparse.ArgumentParser(
        prog="edgar-monitor",
        description="EDGAR Disclosure Monitor â detect material changes in SEC filings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
        Examples:
          edgar-monitor demo --ticker AAPL --verbose
          edgar-monitor score --old filing_v1.txt --new filing_v2.txt --json
          edgar-monitor watch --ticker MSFT --interval 6
        """),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # demo
    d = sub.add_parser("demo", help="Run demo analysis on built-in test data")
    d.add_argument("--ticker", default="AAPL")
    d.add_argument("--verbose", "-v", action="store_true")

    # score
    s = sub.add_parser("score", help="Score materiality of two text files")
    s.add_argument("--old", required=True, help="Path to old filing section")
    s.add_argument("--new", required=True, help="Path to new filing section")
    s.add_argument("--threshold", type=float, default=0.35)
    s.add_argument("--kw-weight", type=float, default=0.5)
    s.add_argument("--snt-weight", type=float, default=0.25)
    s.add_argument("--edit-weight", type=float, default=0.25)
    s.add_argument("--json", action="store_true")

    # watch
    w = sub.add_parser("watch", help="Continuously monitor a ticker")
    w.add_argument("--ticker", required=True)
    w.add_argument("--interval", type=float, default=6.0)

    args = p.parse_args()
    {"demo": cmd_demo, "score": cmd_score, "watch": cmd_watch}[args.cmd](args)


if __name__ == "__main__":
    main()
