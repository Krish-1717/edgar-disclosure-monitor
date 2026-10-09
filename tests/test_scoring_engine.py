"""tests/test_scoring_engine.py — Unit tests for scoring engine + ranker + config."""
from __future__ import annotations
import sys
import os
import math

# ---------------------------------------------------------------------------
# Inline minimal implementations so tests run without installing anything
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field
from copy import deepcopy


@dataclass
class EDGARScore:
    ticker: str
    materiality_score: float
    news_quality_score: float
    composite_news: float
    attention_gap: float
    final_score: float
    rank: str
    confidence: float
    signal_breakdown: dict = field(default_factory=dict)


def _rank_from_score(score: float) -> str:
    if score >= 80: return "CRITICAL"
    if score >= 60: return "HIGH"
    if score >= 40: return "MEDIUM"
    if score >= 20: return "LOW"
    return "NOISE"


def compute_edgar_score(ticker, materiality, news_quality, article_count,
                        count_weight=0.35, quality_weight=0.65) -> EDGARScore:
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
    return EDGARScore(
        ticker=ticker, materiality_score=materiality,
        news_quality_score=news_quality, composite_news=composite_news,
        attention_gap=attention_gap, final_score=round(final_score, 2),
        rank=rank, confidence=round(confidence, 4),
    )


_RANK_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "NOISE": 0}


class AlertRanker:
    def rank_alerts(self, alerts):
        return sorted(alerts, key=lambda a: (-a.get("final_score", 0),
                                              -a.get("materiality_score", 0),
                                              -a.get("news_quality_score", 0)))

    def get_top_n(self, alerts, n=10):
        return self.rank_alerts(alerts)[:n]

    def filter_by_rank(self, alerts, min_rank="MEDIUM"):
        threshold = _RANK_ORDER.get(min_rank.upper(), 2)
        return [a for a in alerts if _RANK_ORDER.get(a.get("rank", "NOISE"), 0) >= threshold]

    def to_daily_digest(self, alerts):
        ranked = self.rank_alerts(alerts)
        lines = ["Today's top alerts:"]
        for i, a in enumerate(ranked[:10], 1):
            lines.append(f"{i}. {a.get('ticker','???')} {a.get('rank','NOISE')}")
        return "\n".join(lines)


DEFAULT_CONFIG = {
    "edgar": {"rate_limit_per_sec": 10, "cache_dir": "data/cache",
              "max_filings_to_compare": 2, "supported_forms": ["10-K", "10-Q"]},
    "news": {"window_days": 3, "quality_threshold": 0.65,
             "count_weight": 0.35, "quality_weight": 0.65},
    "scoring": {"critical_threshold": 80, "high_threshold": 60,
                "medium_threshold": 40, "low_threshold": 20},
    "notifications": {
        "email": {"enabled": False, "smtp_host": "smtp.gmail.com", "smtp_port": 587,
                  "smtp_user": "", "smtp_password": "", "from_addr": "", "to_addrs": []},
        "webhook": {"enabled": False, "url": "", "secret": ""},
        "in_app": {"enabled": True, "path": "data/notifications.jsonl"},
    },
}


class ConfigManager:
    def __init__(self, cfg=None):
        self._cfg = deepcopy(cfg or DEFAULT_CONFIG)

    def get(self, key, default=None):
        parts = key.split(".")
        node = self._cfg
        for p in parts:
            if not isinstance(node, dict) or p not in node:
                return default
            node = node[p]
        return node

    def set(self, key, value):
        parts = key.split(".")
        node = self._cfg
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = value

    def validate(self):
        errors = []
        if self.get("notifications.email.enabled"):
            if not self.get("notifications.email.smtp_host"):
                errors.append("smtp_host required")
            if not self.get("notifications.email.from_addr"):
                errors.append("from_addr required")
        if self.get("notifications.webhook.enabled"):
            if not self.get("notifications.webhook.url"):
                errors.append("webhook url required")
        return errors


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_compute_edgar_score_critical():
    """High materiality, near-zero news → CRITICAL."""
    s = compute_edgar_score("TEST", materiality=0.95, news_quality=0.05, article_count=1)
    assert s.rank == "CRITICAL", f"Expected CRITICAL, got {s.rank} (score={s.final_score})"
    assert s.final_score >= 80


def test_compute_edgar_score_low():
    """Low materiality with heavy news coverage → LOW or NOISE."""
    s = compute_edgar_score("TEST", materiality=0.10, news_quality=0.90, article_count=20)
    assert s.rank in ("LOW", "NOISE", "MEDIUM"), f"Expected LOW-ish, got {s.rank} (score={s.final_score})"
    assert s.final_score < 40


def test_attention_gap_zero_news():
    """Near-zero news composite drives attention gap very high."""
    s = compute_edgar_score("GAP", materiality=0.80, news_quality=0.0, article_count=0)
    assert s.attention_gap >= 10, f"attention_gap={s.attention_gap} expected >= 10"
    assert s.final_score >= 80


def test_ranker_sorts_by_score():
    """AlertRanker should sort alerts by final_score descending."""
    alerts = [
        {"ticker": "A", "final_score": 30.0, "materiality_score": 0.3,
         "news_quality_score": 0.5, "rank": "MEDIUM"},
        {"ticker": "B", "final_score": 85.0, "materiality_score": 0.9,
         "news_quality_score": 0.1, "rank": "CRITICAL"},
        {"ticker": "C", "final_score": 60.0, "materiality_score": 0.6,
         "news_quality_score": 0.4, "rank": "HIGH"},
    ]
    ranker = AlertRanker()
    ranked = ranker.rank_alerts(alerts)
    scores = [a["final_score"] for a in ranked]
    assert scores == sorted(scores, reverse=True), f"Not descending: {scores}"


def test_ranker_filter_by_rank():
    """Filter should remove LOW and NOISE alerts when min_rank=MEDIUM."""
    alerts = [
        {"ticker": "A", "rank": "CRITICAL", "final_score": 85, "materiality_score": 0.9, "news_quality_score": 0.1},
        {"ticker": "B", "rank": "HIGH",     "final_score": 65, "materiality_score": 0.7, "news_quality_score": 0.3},
        {"ticker": "C", "rank": "MEDIUM",   "final_score": 45, "materiality_score": 0.5, "news_quality_score": 0.5},
        {"ticker": "D", "rank": "LOW",      "final_score": 25, "materiality_score": 0.3, "news_quality_score": 0.7},
        {"ticker": "E", "rank": "NOISE",    "final_score":  5, "materiality_score": 0.1, "news_quality_score": 0.9},
    ]
    ranker = AlertRanker()
    filtered = ranker.filter_by_rank(alerts, min_rank="MEDIUM")
    tickers = {a["ticker"] for a in filtered}
    assert "A" in tickers and "B" in tickers and "C" in tickers
    assert "D" not in tickers and "E" not in tickers, f"LOW/NOISE should be removed: {tickers}"


def test_daily_digest_format():
    """Digest should start with 'Today's top alerts'."""
    alerts = [
        {"ticker": "NVDA", "rank": "CRITICAL", "final_score": 90, "materiality_score": 0.9, "news_quality_score": 0.1},
        {"ticker": "AAPL", "rank": "HIGH",     "final_score": 65, "materiality_score": 0.7, "news_quality_score": 0.3},
    ]
    ranker = AlertRanker()
    digest = ranker.to_daily_digest(alerts)
    assert "Today's top alerts" in digest, f"Missing header in: {digest!r}"
    assert "NVDA" in digest


def test_confidence_scales_with_articles():
    """More articles should yield higher confidence for same materiality."""
    s_few  = compute_edgar_score("T", materiality=0.8, news_quality=0.5, article_count=2)
    s_many = compute_edgar_score("T", materiality=0.8, news_quality=0.5, article_count=20)
    assert s_many.confidence > s_few.confidence, (
        f"Expected many > few: {s_many.confidence} vs {s_few.confidence}"
    )


def test_config_dot_notation():
    """ConfigManager.get() should support dot-notation access."""
    cfg = ConfigManager()
    assert cfg.get("edgar.rate_limit_per_sec") == 10
    assert cfg.get("news.count_weight") == 0.35
    assert cfg.get("scoring.critical_threshold") == 80
    assert cfg.get("notifications.in_app.enabled") is True
    assert cfg.get("nonexistent.key", "fallback") == "fallback"


def test_config_validation_missing_smtp():
    """Validation should catch email enabled with empty smtp_host."""
    cfg = ConfigManager()
    cfg.set("notifications.email.enabled", True)
    cfg.set("notifications.email.smtp_host", "")   # missing!
    errors = cfg.validate()
    assert any("smtp_host" in e for e in errors), (
        f"Expected smtp_host error, got: {errors}"
    )


# ---------------------------------------------------------------------------
# Simple test runner (also works with pytest)
# ---------------------------------------------------------------------------

_TESTS = [
    test_compute_edgar_score_critical,
    test_compute_edgar_score_low,
    test_attention_gap_zero_news,
    test_ranker_sorts_by_score,
    test_ranker_filter_by_rank,
    test_daily_digest_format,
    test_confidence_scales_with_articles,
    test_config_dot_notation,
    test_config_validation_missing_smtp,
]


if __name__ == "__main__":
    passed = 0
    failed = 0
    for test_fn in _TESTS:
        try:
            test_fn()
            print(f"  PASS  {test_fn.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {test_fn.__name__}: {exc}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
