"""scoring_engine.py — Unified signal scoring for EDGAR Disclosure Monitor."""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EDGARScore:
    ticker: str
    materiality_score: float       # 0-1, from filing_differ
    news_quality_score: float      # 0-1, from news_importance_scorer
    composite_news: float          # 0.35*count_norm + 0.65*quality
    attention_gap: float           # materiality / max(composite_news, 0.01)
    final_score: float             # calibrated 0-100 score
    rank: str                      # CRITICAL/HIGH/MEDIUM/LOW
    confidence: float              # 0-1 based on data availability
    signal_breakdown: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return (
            f"[{self.rank}] {self.ticker} | score={self.final_score:.1f} "
            f"| materiality={self.materiality_score:.2f} "
            f"| news_quality={self.news_quality_score:.2f} "
            f"| confidence={self.confidence:.2f}"
        )


def _rank_from_score(score: float) -> str:
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    if score >= 20:
        return "LOW"
    return "NOISE"


def compute_edgar_score(
    ticker: str,
    materiality: float,
    news_quality: float,
    article_count: int,
    count_weight: float = 0.35,
    quality_weight: float = 0.65,
) -> EDGARScore:
    """
    Compute a unified EDGAR score from materiality and news signals.

    Formula:
        composite_news = count_weight * min(article_count / 20, 1.0)
                       + quality_weight * news_quality
        attention_gap  = materiality / max(composite_news, 0.01)
        base_score     = min(attention_gap * 100, 100)
        bonus          = +10 if article_count < 5   (hidden information)
        penalty        = -15 if materiality < 0.2   (routine filing)
        final_score    = clamp(base_score + bonus - penalty, 0, 100)
        confidence     = sqrt(min(article_count / 20, 1.0)) * materiality
    """
    materiality = max(0.0, min(1.0, materiality))
    news_quality = max(0.0, min(1.0, news_quality))
    article_count = max(0, article_count)

    count_norm = min(article_count / 20.0, 1.0)
    composite_news = count_weight * count_norm + quality_weight * news_quality
    attention_gap = materiality / max(composite_news, 0.01)

    base_score = min(attention_gap * 100.0, 100.0)
    bonus = 10.0 if article_count < 5 else 0.0
    penalty = 15.0 if materiality < 0.2 else 0.0
    final_score = max(0.0, min(100.0, base_score + bonus - penalty))

    confidence = math.sqrt(min(article_count / 20.0, 1.0)) * materiality
    confidence = max(0.0, min(1.0, confidence))

    rank = _rank_from_score(final_score)
    signal_breakdown = {
        "materiality": round(materiality, 4),
        "news_quality": round(news_quality, 4),
        "composite_news": round(composite_news, 4),
        "attention_gap": round(attention_gap, 4),
        "base_score": round(base_score, 2),
        "bonus": bonus,
        "penalty": penalty,
    }

    return EDGARScore(
        ticker=ticker,
        materiality_score=materiality,
        news_quality_score=news_quality,
        composite_news=composite_news,
        attention_gap=attention_gap,
        final_score=round(final_score, 2),
        rank=rank,
        confidence=round(confidence, 4),
        signal_breakdown=signal_breakdown,
    )


if __name__ == "__main__":
    mock_data = [
        {"ticker": "NVDA", "materiality": 0.92, "news_quality": 0.85, "articles": 18},
        {"ticker": "AAPL", "materiality": 0.75, "news_quality": 0.40, "articles": 3},
        {"ticker": "TSLA", "materiality": 0.30, "news_quality": 0.60, "articles": 25},
        {"ticker": "META", "materiality": 0.88, "news_quality": 0.10, "articles": 1},
        {"ticker": "INTC", "materiality": 0.15, "news_quality": 0.50, "articles": 8},
    ]

    print("=" * 65)
    print("EDGAR Scoring Engine — Demo")
    print("=" * 65)
    scores = []
    for d in mock_data:
        s = compute_edgar_score(
            ticker=d["ticker"],
            materiality=d["materiality"],
            news_quality=d["news_quality"],
            article_count=d["articles"],
        )
        scores.append(s)
        print(s)
        print(f"  breakdown: {s.signal_breakdown}\n")

    print("\nRanked by final_score:")
    for s in sorted(scores, key=lambda x: x.final_score, reverse=True):
        print(f"  {s.ticker:6s} {s.final_score:5.1f}  [{s.rank}]")
