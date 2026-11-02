"""
sector_heatmap.py — Sector-level risk aggregation from filing scores and news.

Maps individual ticker risk scores to GICS sectors, computes sector-level
composite risk, and provides JSON/CSV export for dashboard integration.

Usage:
    heatmap = SectorHeatmap()
    scores  = {"NVDA": 0.85, "AAPL": 0.42, "JPM": 0.61, "XOM": 0.33}
    result  = heatmap.compute(scores)
    print(heatmap.to_json(result))
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# GICS sector taxonomy
# ---------------------------------------------------------------------------

GICS_SECTORS = [
    "Technology",
    "Financials",
    "Healthcare",
    "Consumer Discretionary",
    "Consumer Staples",
    "Industrials",
    "Energy",
    "Materials",
    "Real Estate",
    "Utilities",
    "Communication Services",
    "Unknown",
]

# 80+ ticker → GICS sector mapping
TICKER_TO_SECTOR: dict[str, str] = {
    # Technology
    "AAPL":  "Technology",
    "MSFT":  "Technology",
    "NVDA":  "Technology",
    "AMD":   "Technology",
    "INTC":  "Technology",
    "QCOM":  "Technology",
    "TXN":   "Technology",
    "MU":    "Technology",
    "AMAT":  "Technology",
    "KLAC":  "Technology",
    "LRCX":  "Technology",
    "MRVL":  "Technology",
    "AVGO":  "Technology",
    "ADI":   "Technology",
    "ON":    "Technology",
    "ASML":  "Technology",
    "TSM":   "Technology",
    "IBM":   "Technology",
    "ORCL":  "Technology",
    "SAP":   "Technology",
    "CRM":   "Technology",
    "ADBE":  "Technology",
    "NOW":   "Technology",
    "SNOW":  "Technology",
    "PLTR":  "Technology",
    "DDOG":  "Technology",
    # Communication Services
    "GOOGL": "Communication Services",
    "GOOG":  "Communication Services",
    "META":  "Communication Services",
    "NFLX":  "Communication Services",
    "DIS":   "Communication Services",
    "CMCSA": "Communication Services",
    "T":     "Communication Services",
    "VZ":    "Communication Services",
    "TMUS":  "Communication Services",
    "SNAP":  "Communication Services",
    "PINS":  "Communication Services",
    "SPOT":  "Communication Services",
    # Consumer Discretionary
    "AMZN":  "Consumer Discretionary",
    "TSLA":  "Consumer Discretionary",
    "HD":    "Consumer Discretionary",
    "LOW":   "Consumer Discretionary",
    "MCD":   "Consumer Discretionary",
    "SBUX":  "Consumer Discretionary",
    "NKE":   "Consumer Discretionary",
    "F":     "Consumer Discretionary",
    "GM":    "Consumer Discretionary",
    "RIVN":  "Consumer Discretionary",
    "LCID":  "Consumer Discretionary",
    "TGT":   "Consumer Discretionary",
    # Consumer Staples
    "WMT":   "Consumer Staples",
    "COST":  "Consumer Staples",
    "PG":    "Consumer Staples",
    "KO":    "Consumer Staples",
    "PEP":   "Consumer Staples",
    "PM":    "Consumer Staples",
    "MO":    "Consumer Staples",
    "MDLZ":  "Consumer Staples",
    # Financials
    "JPM":   "Financials",
    "BAC":   "Financials",
    "WFC":   "Financials",
    "C":     "Financials",
    "GS":    "Financials",
    "MS":    "Financials",
    "BLK":   "Financials",
    "SCHW":  "Financials",
    "AXP":   "Financials",
    "V":     "Financials",
    "MA":    "Financials",
    "PNC":   "Financials",
    "USB":   "Financials",
    "SVB":   "Financials",
    "SIVB":  "Financials",
    "FRC":   "Financials",
    # Healthcare
    "JNJ":   "Healthcare",
    "UNH":   "Healthcare",
    "PFE":   "Healthcare",
    "MRK":   "Healthcare",
    "ABT":   "Healthcare",
    "LLY":   "Healthcare",
    "BMY":   "Healthcare",
    "AMGN":  "Healthcare",
    "BIIB":  "Healthcare",
    "GILD":  "Healthcare",
    "MDT":   "Healthcare",
    "ISRG":  "Healthcare",
    "DXCM":  "Healthcare",
    # Energy
    "XOM":   "Energy",
    "CVX":   "Energy",
    "COP":   "Energy",
    "SLB":   "Energy",
    "OXY":   "Energy",
    "MPC":   "Energy",
    "VLO":   "Energy",
    "PSX":   "Energy",
    "HAL":   "Energy",
    # Industrials
    "BA":    "Industrials",
    "CAT":   "Industrials",
    "HON":   "Industrials",
    "GE":    "Industrials",
    "LMT":   "Industrials",
    "RTX":   "Industrials",
    "NOC":   "Industrials",
    "UNP":   "Industrials",
    "FDX":   "Industrials",
    "UPS":   "Industrials",
    # Materials
    "FCX":   "Materials",
    "NEM":   "Materials",
    "ALB":   "Materials",
    "LIN":   "Materials",
    # Real Estate
    "AMT":   "Real Estate",
    "PLD":   "Real Estate",
    "EQIX":  "Real Estate",
    # Utilities
    "NEE":   "Utilities",
    "DUK":   "Utilities",
    "SO":    "Utilities",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class TickerRisk:
    ticker: str
    sector: str
    score: float      # 0-1 risk score
    source: str = ""  # "filing" | "news" | "combined"


@dataclass
class SectorRisk:
    sector: str
    tickers: list = field(default_factory=list)
    avg_score: float = 0.0
    max_score: float = 0.0
    min_score: float = 0.0
    ticker_count: int = 0
    high_risk_count: int = 0    # tickers with score >= 0.7
    risk_level: str = "LOW"     # LOW | MEDIUM | HIGH | CRITICAL

    def __post_init__(self):
        if self.avg_score >= 0.85:
            self.risk_level = "CRITICAL"
        elif self.avg_score >= 0.65:
            self.risk_level = "HIGH"
        elif self.avg_score >= 0.40:
            self.risk_level = "MEDIUM"
        else:
            self.risk_level = "LOW"


@dataclass
class HeatmapResult:
    sectors: dict            # sector_name -> SectorRisk
    ticker_risks: list       # list[TickerRisk]
    overall_risk: float      # portfolio-wide average
    hottest_sector: str
    coldest_sector: str
    generated_at: str


# ---------------------------------------------------------------------------
# Sector Heatmap
# ---------------------------------------------------------------------------

class SectorHeatmap:
    """
    Aggregates ticker-level risk scores into sector-level heatmap data.

    Supports both filing risk scores (from RiskScorer) and news relevance
    scores (from NewsRelevanceRanker), or any custom 0-1 score dict.
    """

    def __init__(self, ticker_map: dict = None):
        self.ticker_map = ticker_map or TICKER_TO_SECTOR

    def get_sector(self, ticker: str) -> str:
        return self.ticker_map.get(ticker.upper(), "Unknown")

    def compute(
        self,
        ticker_scores: dict,
        source: str = "combined",
    ) -> HeatmapResult:
        """
        Compute sector-level risk from {ticker: score} dict.

        Args:
            ticker_scores: dict mapping ticker symbol -> float (0-1)
            source: label for the score source ('filing'|'news'|'combined')

        Returns:
            HeatmapResult with per-sector SectorRisk objects
        """
        ticker_risks: list = []
        sector_buckets: dict = {s: [] for s in GICS_SECTORS}

        for ticker, score in ticker_scores.items():
            score = max(0.0, min(float(score), 1.0))
            sector = self.get_sector(ticker)
            tr = TickerRisk(ticker=ticker.upper(), sector=sector,
                            score=round(score, 4), source=source)
            ticker_risks.append(tr)
            sector_buckets[sector].append(tr)

        sectors: dict = {}
        for sector_name, trs in sector_buckets.items():
            if not trs:
                continue
            scores = [tr.score for tr in trs]
            sr = SectorRisk(
                sector=sector_name,
                tickers=[tr.ticker for tr in sorted(trs, key=lambda x: -x.score)],
                avg_score=round(sum(scores) / len(scores), 4),
                max_score=round(max(scores), 4),
                min_score=round(min(scores), 4),
                ticker_count=len(trs),
                high_risk_count=sum(1 for s in scores if s >= 0.7),
            )
            sectors[sector_name] = sr

        if not sectors:
            return HeatmapResult(
                sectors={}, ticker_risks=[], overall_risk=0.0,
                hottest_sector="", coldest_sector="",
                generated_at=datetime.utcnow().isoformat(),
            )

        all_avgs = {k: v.avg_score for k, v in sectors.items()}
        overall = round(sum(all_avgs.values()) / len(all_avgs), 4)
        hottest = max(all_avgs, key=all_avgs.get)
        coldest = min(all_avgs, key=all_avgs.get)

        return HeatmapResult(
            sectors=sectors,
            ticker_risks=sorted(ticker_risks, key=lambda x: -x.score),
            overall_risk=overall,
            hottest_sector=hottest,
            coldest_sector=coldest,
            generated_at=datetime.utcnow().isoformat(),
        )

    def merge(self, filing_scores: dict, news_scores: dict,
              filing_weight: float = 0.6) -> dict:
        """
        Combine filing and news scores into a single weighted ticker score dict.

        Args:
            filing_scores: {ticker: score} from RiskScorer
            news_scores: {ticker: score} from NewsRelevanceRanker
            filing_weight: weight for filing scores (news = 1 - filing_weight)
        """
        news_weight = 1.0 - filing_weight
        all_tickers = set(filing_scores) | set(news_scores)
        combined = {}
        for ticker in all_tickers:
            fs = filing_scores.get(ticker, 0.0)
            ns = news_scores.get(ticker, 0.0)
            combined[ticker] = round(fs * filing_weight + ns * news_weight, 4)
        return combined

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def to_json(self, result: HeatmapResult, path: Optional[Path] = None) -> str:
        data = {
            "overall_risk": result.overall_risk,
            "hottest_sector": result.hottest_sector,
            "coldest_sector": result.coldest_sector,
            "generated_at": result.generated_at,
            "sectors": {
                name: asdict(sr) for name, sr in result.sectors.items()
            },
            "ticker_risks": [asdict(tr) for tr in result.ticker_risks],
        }
        out = json.dumps(data, indent=2)
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(out)
        return out

    def to_csv(self, result: HeatmapResult, path: Path) -> None:
        """Export sector summary to CSV."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "sector", "avg_score", "max_score", "min_score",
                "ticker_count", "high_risk_count", "risk_level", "tickers"
            ])
            writer.writeheader()
            for sr in sorted(result.sectors.values(), key=lambda x: -x.avg_score):
                writer.writerow({
                    "sector": sr.sector,
                    "avg_score": sr.avg_score,
                    "max_score": sr.max_score,
                    "min_score": sr.min_score,
                    "ticker_count": sr.ticker_count,
                    "high_risk_count": sr.high_risk_count,
                    "risk_level": sr.risk_level,
                    "tickers": ", ".join(sr.tickers[:10]),
                })

    def print_table(self, result: HeatmapResult) -> None:
        """Pretty-print the heatmap to stdout."""
        COLORS = {"CRITICAL": "\033[91m", "HIGH": "\033[93m",
                  "MEDIUM": "\033[94m", "LOW": "\033[92m", "RESET": "\033[0m"}
        print(f"\n{'EDGAR SECTOR RISK HEATMAP':^70}")
        print(f"{'Overall risk: ' + str(result.overall_risk):^70}")
        print(f"{'Generated: ' + result.generated_at[:19]:^70}\n")
        print(f"{'Sector':<28} {'Avg':>6} {'Max':>6} {'#':>4} {'High':>5}  Level")
        print("-" * 70)
        for sr in sorted(result.sectors.values(), key=lambda x: -x.avg_score):
            color = COLORS.get(sr.risk_level, "")
            reset = COLORS["RESET"]
            print(f"{color}{sr.sector:<28} {sr.avg_score:>6.3f} {sr.max_score:>6.3f} "
                  f"{sr.ticker_count:>4} {sr.high_risk_count:>5}  {sr.risk_level}{reset}")


if __name__ == "__main__":
    heatmap = SectorHeatmap()
    demo_scores = {
        "NVDA": 0.85, "AAPL": 0.42, "MSFT": 0.38, "META": 0.61, "GOOGL": 0.35,
        "JPM":  0.71, "BAC":  0.65, "GS":   0.55, "SVB":  0.97,
        "XOM":  0.33, "CVX":  0.28,
        "LLY":  0.45, "JNJ":  0.52, "PFE":  0.25,
        "TSLA": 0.79, "F":    0.48, "GM":   0.41,
        "BA":   0.82, "CAT":  0.22,
    }
    result = heatmap.compute(demo_scores, source="demo")
    heatmap.print_table(result)
    heatmap.to_json(result, Path("data/sector_heatmap.json"))
    print(f"\nHottest sector: {result.hottest_sector}")
    print(f"Coldest sector: {result.coldest_sector}")
