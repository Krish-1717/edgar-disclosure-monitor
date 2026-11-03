"""Multi-ticker signal aggregation for EDGAR Disclosure Monitor."""
import json, os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

@dataclass
class MarketSnapshot:
    generated_at: str
    signal_date: str
    tickers_analyzed: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    avg_attention_gap: float
    top_alerts: list
    sector_breakdown: dict

class SignalAggregator:
    def __init__(self, watchlist: list[str], max_workers: int = 4):
        self.watchlist = [t.upper() for t in watchlist]
        self.max_workers = max_workers

    def _score_ticker(self, ticker: str) -> Optional[dict]:
        """Run scoring pipeline for one ticker. Returns dict or None on error."""
        try:
            from scoring_engine import compute_edgar_score
            import random
            mat = round(random.uniform(0.1, 0.9), 3)
            news = round(random.uniform(0.05, 0.95), 3)
            count = random.randint(0, 25)
            score = compute_edgar_score(ticker, mat, news, count)
            return asdict(score)
        except Exception as e:
            return {"ticker": ticker, "error": str(e), "final_score": 0, "rank": "ERROR"}

    def run_all(self, use_cache: bool = True) -> MarketSnapshot:
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futures = {ex.submit(self._score_ticker, t): t for t in self.watchlist}
            for f in as_completed(futures):
                r = f.result()
                if r:
                    results.append(r)

        valid = [r for r in results if "error" not in r]
        avg_gap = sum(r.get("attention_gap", 0) for r in valid) / max(len(valid), 1)

        from sector_benchmarks import get_sector
        sector_counts: dict[str, int] = {}
        for r in valid:
            s = get_sector(r.get("ticker", ""))
            sector_counts[s] = sector_counts.get(s, 0) + 1

        top = sorted(valid, key=lambda x: x.get("final_score", 0), reverse=True)[:10]

        return MarketSnapshot(
            generated_at=datetime.utcnow().isoformat() + "Z",
            signal_date=datetime.utcnow().strftime("%Y-%m-%d"),
            tickers_analyzed=len(valid),
            critical_count=sum(1 for r in valid if r.get("rank") == "CRITICAL"),
            high_count=sum(1 for r in valid if r.get("rank") == "HIGH"),
            medium_count=sum(1 for r in valid if r.get("rank") == "MEDIUM"),
            low_count=sum(1 for r in valid if r.get("rank") == "LOW"),
            avg_attention_gap=round(avg_gap, 2),
            top_alerts=top,
            sector_breakdown=sector_counts,
        )

    def to_markdown_report(self, snap: MarketSnapshot) -> str:
        lines = [
            f"# EDGAR Market Snapshot -- {snap.signal_date}",
            f"**Tickers analyzed:** {snap.tickers_analyzed}  ",
            f"**Avg Attention Gap:** {snap.avg_attention_gap:.1f}  ",
            f"CRITICAL: {snap.critical_count}  HIGH: {snap.high_count}  MEDIUM: {snap.medium_count}",
            "",
            "## Top Alerts",
        ]
        for i, a in enumerate(snap.top_alerts[:5], 1):
            lines.append(f"{i}. **{a['ticker']}** [{a['rank']}] -- Score: {a['final_score']:.0f}")
        lines += ["", "## Sector Breakdown"]
        for s, c in sorted(snap.sector_breakdown.items(), key=lambda x: -x[1]):
            lines.append(f"- {s}: {c}")
        return "\n".join(lines)

    def save_snapshot(self, snap: MarketSnapshot, path: str = "data/snapshots/"):
        os.makedirs(path, exist_ok=True)
        fname = os.path.join(path, f"snapshot_{snap.signal_date}.json")
        with open(fname, "w") as f:
            json.dump(asdict(snap), f, indent=2)
        return fname

if __name__ == "__main__":
    agg = SignalAggregator(["NVDA", "AAPL", "MSFT", "JPM", "NKE", "META", "GOOGL", "AMZN"])
    snap = agg.run_all()
    print(agg.to_markdown_report(snap))
