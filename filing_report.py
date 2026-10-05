"""
filing_report.py — Report generator for FilingDiff results.

Provides:
    generate_text_report(diff) -> str       ASCII report
    generate_json_report(diff) -> dict      Full structured JSON
    generate_alert_payload(diff, ...) -> dict   Frontend ALERTS schema

CLI:
    python filing_report.py --ticker AAPL --form 10-K
"""
from __future__ import annotations

import argparse
import json
from typing import Optional

from filing_differ import FilingDiff, ItemDiff

# ── Rank mapping ────────────────────────────────────────────────────────────────

def _rank_label(materiality_pct: float) -> str:
    if materiality_pct >= 80:
        return "CRITICAL"
    elif materiality_pct >= 60:
        return "HIGH"
    elif materiality_pct >= 40:
        return "MEDIUM"
    elif materiality_pct >= 20:
        return "LOW"
    return "MINIMAL"


def _rank_number(materiality_pct: float) -> int:
    if materiality_pct >= 80:
        return 1
    elif materiality_pct >= 60:
        return 2
    elif materiality_pct >= 40:
        return 3
    elif materiality_pct >= 20:
        return 4
    return 5


# ── Text report ─────────────────────────────────────────────────────────────────

def generate_text_report(diff: FilingDiff) -> str:
    """Return an ASCII text report of the filing diff."""
    lines = []
    sep = "=" * 72

    lines.append(sep)
    lines.append(f"  SEC FILING DIFF REPORT — {diff.ticker}")
    lines.append(sep)
    lines.append(f"  Old filing : {diff.old_filing.filed_date}  ({diff.old_filing.form_type})")
    lines.append(f"  New filing : {diff.new_filing.filed_date}  ({diff.new_filing.form_type})")
    lines.append(f"  Overall materiality : {diff.overall_materiality:.3f}  "
                 f"({_rank_label(diff.overall_materiality * 100)})")
    lines.append(f"  Top changed items  : {', '.join(diff.top_changed_items)}")
    lines.append("")

    top_diffs = diff.get_top_changes(10)
    for d in top_diffs:
        pct = d.materiality_score * 100
        bar_len = max(1, int(pct / 5))
        bar = "█" * bar_len + "░" * (20 - bar_len)
        lines.append(f"  Item {d.item_num:<6} [{bar}] {pct:5.1f}%  "
                     f"sim={d.similarity:.2f}  Δwords={d.word_delta:+.2f}  "
                     f"hedge={d.hedging_shift:+.3f}")
        if d.added_sentences:
            lines.append("    ▲ Added (top 2):")
            for sent in d.added_sentences[:2]:
                lines.append(f"      + {sent[:120]}")
        if d.removed_sentences:
            lines.append("    ▼ Removed (top 2):")
            for sent in d.removed_sentences[:2]:
                lines.append(f"      - {sent[:120]}")
        lines.append("")

    lines.append(sep)
    return "\n".join(lines)


# ── JSON report ─────────────────────────────────────────────────────────────────

def generate_json_report(diff: FilingDiff) -> dict:
    """Return a full structured JSON-serialisable report."""
    item_reports = {}
    for num, d in diff.item_diffs.items():
        item_reports[num] = {
            "item_num": d.item_num,
            "materiality_score": d.materiality_score,
            "similarity": d.similarity,
            "word_delta": d.word_delta,
            "hedging_shift": d.hedging_shift,
            "added_sentences": d.added_sentences[:10],
            "removed_sentences": d.removed_sentences[:10],
            "number_changes": d.number_changes[:10],
        }

    return {
        "ticker": diff.ticker,
        "old_filing": {
            "filed_date": diff.old_filing.filed_date,
            "form_type": diff.old_filing.form_type,
            "accession": diff.old_filing.accession,
        },
        "new_filing": {
            "filed_date": diff.new_filing.filed_date,
            "form_type": diff.new_filing.form_type,
            "accession": diff.new_filing.accession,
        },
        "overall_materiality": diff.overall_materiality,
        "rank": _rank_label(diff.overall_materiality * 100),
        "top_changed_items": diff.top_changed_items,
        "item_diffs": item_reports,
    }


# ── Alert payload (matches frontend ALERTS schema) ──────────────────────────────

def generate_alert_payload(
    diff: FilingDiff,
    news_score: float = 0.5,
    sentiment: str = "NEUTRAL",
    bucket: Optional[str] = None,
) -> dict:
    """
    Return a dict matching the frontend ALERTS schema exactly.

    Keys: id, ticker, company, sector, form, filed, rank, ranking,
          materiality, burial, gap, sentiment, bucket, item, desc,
          old_text, new_text
    """
    mat_pct = diff.overall_materiality * 100
    rank_label = _rank_label(mat_pct)
    rank_num = _rank_number(mat_pct)

    # Attention gap: how much materiality exceeds news coverage
    gap = min(100.0, mat_pct / max(news_score, 0.01))

    # Top changed item for display
    top_diffs = diff.get_top_changes(1)
    top_item = top_diffs[0] if top_diffs else None

    item_num = top_item.item_num if top_item else "N/A"
    desc = ""
    old_text = ""
    new_text = ""

    if top_item:
        if top_item.added_sentences:
            new_text = top_item.added_sentences[0][:500]
        if top_item.removed_sentences:
            old_text = top_item.removed_sentences[0][:500]
        desc = (
            f"Item {item_num} changed: similarity={top_item.similarity:.2f}, "
            f"word_delta={top_item.word_delta:+.1%}, hedging_shift={top_item.hedging_shift:+.3f}"
        )

    # Burial score: higher similarity in top items → more buried
    burial = round((1.0 - (top_item.similarity if top_item else 0.5)) * 100, 1)

    return {
        "id": f"{diff.ticker}_{diff.new_filing.accession}",
        "ticker": diff.ticker,
        "company": diff.ticker,       # enriched downstream if company name known
        "sector": "Unknown",          # enriched downstream
        "form": diff.new_filing.form_type,
        "filed": diff.new_filing.filed_date,
        "rank": rank_label,
        "ranking": rank_num,
        "materiality": round(mat_pct, 1),
        "burial": burial,
        "gap": round(gap, 1),
        "sentiment": sentiment,
        "bucket": bucket or "neutral",
        "item": item_num,
        "desc": desc,
        "old_text": old_text,
        "new_text": new_text,
    }


# ── CLI ─────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate filing diff reports")
    parser.add_argument("--ticker", required=True, help="Stock ticker, e.g. AAPL")
    parser.add_argument("--form", default="10-K", help="Form type: 10-K or 10-Q")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    from filing_fetcher import FilingFetcher
    from filing_parser import parse_filing
    from filing_differ import diff_filings

    fetcher = FilingFetcher()
    old_meta, new_meta = fetcher.get_two_most_recent(args.ticker, args.form)
    old_parsed = parse_filing(old_meta)
    new_parsed = parse_filing(new_meta)
    diff = diff_filings(old_parsed, new_parsed)

    if args.json:
        print(json.dumps(generate_json_report(diff), indent=2))
    else:
        print(generate_text_report(diff))


if __name__ == "__main__":
    main()
