"""alert_ranker.py — Priority-ranked alert queue for EDGAR Disclosure Monitor."""
from __future__ import annotations
import json
import os
from datetime import datetime
from typing import Optional

try:
    from scoring_engine import compute_edgar_score, EDGARScore, _rank_from_score
except ImportError:
    pass

_RANK_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "NOISE": 0}
_MIN_RANK_MAP = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "NOISE": 0}


class AlertRanker:
    """Re-rank a list of alert dicts using the EDGAR scoring engine."""

    def rank_alerts(self, alerts: list[dict]) -> list[dict]:
        """Sort by: final_score DESC, then materiality DESC, then news_quality DESC."""
        def sort_key(a: dict):
            return (
                -a.get("final_score", 0),
                -a.get("materiality_score", 0),
                -a.get("news_quality_score", 0),
            )
        return sorted(alerts, key=sort_key)

    def get_top_n(self, alerts: list[dict], n: int = 10) -> list[dict]:
        """Return top N ranked alerts with rank index (1-based)."""
        ranked = self.rank_alerts(alerts)[:n]
        for i, alert in enumerate(ranked, start=1):
            alert = dict(alert)
            alert["rank_index"] = i
            ranked[i - 1] = alert
        return ranked

    def filter_by_rank(self, alerts: list[dict], min_rank: str = "MEDIUM") -> list[dict]:
        """Filter to alerts at or above min_rank (CRITICAL, HIGH, MEDIUM, LOW)."""
        threshold = _MIN_RANK_MAP.get(min_rank.upper(), 2)
        return [
            a for a in alerts
            if _RANK_ORDER.get(a.get("rank", "NOISE"), 0) >= threshold
        ]

    def to_daily_digest(self, alerts: list[dict]) -> str:
        """Plain-text daily digest of ranked alerts."""
        ranked = self.rank_alerts(alerts)
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        lines = [f"Today's top alerts ({date_str}):"]
        for i, alert in enumerate(ranked[:10], start=1):
            ticker = alert.get("ticker", "???")
            rank = alert.get("rank", "NOISE")
            score = alert.get("final_score", 0)
            mat = alert.get("materiality_score", 0)
            lines.append(
                f"{i:2d}. {ticker:6s} [{rank:8s}] score={score:.1f}  "
                f"materiality={mat:.2f}"
            )
        if not ranked:
            lines.append("  (no alerts)")
        return "\n".join(lines)

    def export_json(self, alerts: list[dict], path: str = "data/ranked_alerts.json") -> None:
        """Save ranked alerts to JSON."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        ranked = self.rank_alerts(alerts)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"generated_at": datetime.utcnow().isoformat(), "alerts": ranked}, fh, indent=2)
        print(f"Exported {len(ranked)} alerts → {path}")


def _make_mock_alerts() -> list[dict]:
    """12 mock alerts mirroring the frontend demo data."""
    rows = [
        ("NVDA", 0.92, 0.85, 18),
        ("META", 0.88, 0.10,  1),
        ("AAPL", 0.75, 0.40,  3),
        ("AMZN", 0.70, 0.55, 12),
        ("MSFT", 0.65, 0.70, 20),
        ("TSLA", 0.30, 0.60, 25),
        ("GOOGL",0.80, 0.20,  4),
        ("NFLX", 0.55, 0.45,  7),
        ("AMD",  0.60, 0.30,  2),
        ("INTC", 0.15, 0.50,  8),
        ("ORCL", 0.40, 0.35,  5),
        ("IBM",  0.20, 0.65, 15),
    ]
    alerts = []
    for ticker, mat, nq, cnt in rows:
        import math
        composite = 0.35 * min(cnt / 20, 1.0) + 0.65 * nq
        gap = mat / max(composite, 0.01)
        base = min(gap * 100, 100)
        bonus = 10.0 if cnt < 5 else 0.0
        penalty = 15.0 if mat < 0.2 else 0.0
        final = max(0.0, min(100.0, base + bonus - penalty))
        rank_map = [(80, "CRITICAL"), (60, "HIGH"), (40, "MEDIUM"), (20, "LOW")]
        rank = "NOISE"
        for thresh, r in rank_map:
            if final >= thresh:
                rank = r
                break
        conf = math.sqrt(min(cnt / 20, 1.0)) * mat
        alerts.append({
            "ticker": ticker,
            "materiality_score": round(mat, 4),
            "news_quality_score": round(nq, 4),
            "composite_news": round(composite, 4),
            "attention_gap": round(gap, 4),
            "final_score": round(final, 2),
            "rank": rank,
            "confidence": round(conf, 4),
            "article_count": cnt,
        })
    return alerts


if __name__ == "__main__":
    ranker = AlertRanker()
    alerts = _make_mock_alerts()

    print("=" * 65)
    print("AlertRanker — Demo (12 mock alerts)")
    print("=" * 65)

    top10 = ranker.get_top_n(alerts, n=10)
    print("\nTop 10 alerts:")
    for a in top10:
        print(f"  #{a['rank_index']:2d} {a['ticker']:6s} [{a['rank']:8s}] "
              f"score={a['final_score']:5.1f}  mat={a['materiality_score']:.2f}")

    print("\nFiltered (MEDIUM+):")
    filtered = ranker.filter_by_rank(alerts, min_rank="MEDIUM")
    print(f"  {len(filtered)} of {len(alerts)} alerts pass")

    print("\n" + ranker.to_daily_digest(alerts))
