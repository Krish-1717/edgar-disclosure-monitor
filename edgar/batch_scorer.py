"""
edgar/batch_scorer.py -- Batch materiality scoring for multiple EDGAR filings
edgar-disclosure-monitor Day 11
"""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from edgar.nlp_scorer import NLPScorer, MaterialityResult


@dataclass
class FilingPair:
    ticker: str
    section: str
    old_text: str
    new_text: str
    filing_date: Optional[str] = None
    form_type: str = "10-K"


@dataclass
class BatchResult:
    ticker: str
    section: str
    materiality: float
    is_material: bool
    keyword_score: float
    sentiment_delta: float
    structural_change: float
    keywords_found: List[str]
    filing_date: Optional[str]
    elapsed_ms: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BatchReport:
    results: List[BatchResult] = field(default_factory=list)
    total_elapsed_ms: float = 0.0
    n_material: int = 0
    n_total: int = 0

    @property
    def materiality_rate(self) -> float:
        return self.n_material / max(self.n_total, 1)

    def top_material(self, n: int = 5) -> List[BatchResult]:
        return sorted(self.results, key=lambda r: -r.materiality)[:n]

    def by_ticker(self) -> Dict[str, List[BatchResult]]:
        out: Dict[str, List[BatchResult]] = {}
        for r in self.results:
            out.setdefault(r.ticker, []).append(r)
        return out

    def to_json(self, indent: int = 2) -> str:
        return json.dumps({
            "summary": {
                "n_total": self.n_total,
                "n_material": self.n_material,
                "materiality_rate": round(self.materiality_rate, 4),
                "total_elapsed_ms": round(self.total_elapsed_ms, 1),
            },
            "results": [r.to_dict() for r in self.results],
        }, indent=indent)

    def print_report(self, verbose: bool = False) -> None:
        print(f"\n{'='*70}")
        print(f"  EDGAR Batch Materiality Report")
        print(f"  {self.n_total} filings scored | {self.n_material} material "
              f"({self.materiality_rate:.1%}) | {self.total_elapsed_ms:.0f}ms total")
        print(f"{'='*70}")
        header = f"  {'Ticker':<8}  {'Section':<22}  {'Score':>6}  {'Flag':<10}  Keywords"
        print(header)
        print(f"  {'-'*8}  {'-'*22}  {'-'*6}  {'-'*10}  {'-'*20}")
        for r in sorted(self.results, key=lambda x: -x.materiality):
            flag = "â  MATERIAL" if r.is_material else "â OK"
            kws = ", ".join(r.keywords_found[:3]) if r.keywords_found else "-"
            print(f"  {r.ticker:<8}  {r.section:<22}  {r.materiality:>6.3f}  {flag:<10}  {kws}")
        if self.n_material > 0:
            print(f"\n  ACTION REQUIRED: {self.n_material} section(s) flagged as material")


class BatchScorer:
    """Score multiple filing section pairs concurrently."""

    def __init__(self, scorer: Optional[NLPScorer] = None,
                 threshold: float = 0.35):
        self.scorer = scorer or NLPScorer()
        self.threshold = threshold

    def score_batch(self, filings: List[FilingPair]) -> BatchReport:
        """Score a list of filing pairs and return aggregated BatchReport."""
        report = BatchReport()
        t0_total = time.monotonic()

        for fp in filings:
            t0 = time.monotonic()
            result: MaterialityResult = self.scorer.score(fp.old_text, fp.new_text)
            elapsed_ms = (time.monotonic() - t0) * 1000
            is_mat = result.is_material(self.threshold)
            br = BatchResult(
                ticker=fp.ticker,
                section=fp.section,
                materiality=round(result.materiality, 5),
                is_material=is_mat,
                keyword_score=round(result.keyword_score, 5),
                sentiment_delta=round(result.sentiment_delta, 5),
                structural_change=round(result.structural_change, 5),
                keywords_found=result.keywords_found,
                filing_date=fp.filing_date,
                elapsed_ms=round(elapsed_ms, 2),
            )
            report.results.append(br)
            if is_mat:
                report.n_material += 1

        report.n_total = len(filings)
        report.total_elapsed_ms = (time.monotonic() - t0_total) * 1000
        return report

    def score_from_dict(self, data: List[dict]) -> BatchReport:
        """Convenience: parse list of dicts into FilingPairs and score."""
        filings = [
            FilingPair(
                ticker=d["ticker"],
                section=d["section"],
                old_text=d["old_text"],
                new_text=d["new_text"],
                filing_date=d.get("filing_date"),
                form_type=d.get("form_type", "10-K"),
            )
            for d in data
        ]
        return self.score_batch(filings)

    def load_and_score_jsonl(self, path: str) -> BatchReport:
        """Load JSONL file (one filing pair per line) and score."""
        filings = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    filings.append(FilingPair(**json.loads(line)))
        return self.score_batch(filings)
