"""
news_relevance_ranker.py — News relevance ranking engine.

Ranks incoming news articles by relevance to a user's active pings and
watchlist. Uses backtested keyword weights (which past news items caused
price moves or EDGAR disclosures to shift), source authority scores,
recency decay, and ticker overlap.

No AI summarization. Ranking is deterministic and auditable.

Pipeline:
  1. Receive batch of NewsArticle objects
  2. Score each against user's active pings (TopicPinger)
  3. Apply source authority multiplier (WSJ > blog)
  4. Apply recency decay (exponential half-life = 6h)
  5. Apply backtested keyword weight boosts
  6. Return ranked list with explanations
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from topic_pinger import TopicPinger, Ping, PRIORITY_WEIGHTS


# ---------------------------------------------------------------------------
# Source authority scores (1–5 tier system)
# ---------------------------------------------------------------------------

SOURCE_AUTHORITY: dict[str, float] = {
    "wsj":         1.00,   # Wall Street Journal — highest
    "nytimes":     0.95,
    "ft":          0.95,   # Financial Times
    "reuters":     0.90,
    "apnews":      0.88,
    "bloomberg":   0.92,
    "cnbc":        0.75,
    "marketwatch": 0.70,
    "sec_news":    1.00,   # SEC press releases — authoritative by definition
    "seeking_alpha": 0.55,
    "yahoo_finance": 0.60,
    "unknown":     0.40,
}

# Recency half-life in hours — news older than this is at 50% score
RECENCY_HALF_LIFE_H = 6.0

# Max recency boost window (articles older than this get asymptotic decay)
MAX_AGE_H = 72.0


# ---------------------------------------------------------------------------
# Backtested keyword boost weights
# (pre-seeded from historical impact analysis — see news_backtest_validator.py)
# ---------------------------------------------------------------------------

KEYWORD_BOOST_WEIGHTS: dict[str, float] = {
    # High-impact market-moving terms
    "bankruptcy":        2.0,
    "fraud":             2.0,
    "sec investigation": 2.0,
    "restatement":       2.0,
    "going concern":     2.0,
    "default":           1.8,
    "acquisition":       1.6,
    "merger":            1.6,
    "hostile takeover":  1.8,
    "fda approval":      1.7,
    "fda rejection":     1.9,
    "recall":            1.6,
    "earnings miss":     1.5,
    "earnings beat":     1.4,
    "guidance cut":      1.7,
    "guidance raise":    1.5,
    "layoffs":           1.4,
    "ceo resign":        1.6,
    "ceo fired":         1.8,
    "sanctions":         1.5,
    "tariff":            1.4,
    "rate hike":         1.4,
    "rate cut":          1.4,
    "quantitative tightening": 1.3,
    "inflation":         1.2,
    "recession":         1.5,
    "war":               1.6,
    "iran":              1.3,
    "china":             1.2,
    "russia":            1.2,
    "taiwan":            1.4,
    "opec":              1.3,
    "supply chain":      1.2,
    "cybersecurity breach": 1.7,
    "data breach":       1.7,
    "antitrust":         1.5,
    "class action":      1.4,
    "insider trading":   1.9,
    "short seller":      1.5,
    "ipo":               1.2,
    "spinoff":           1.3,
    "dividend cut":      1.6,
    "dividend raise":    1.2,
    "buyback":           1.2,
    "debt downgrade":    1.7,
    "credit rating":     1.4,
    "subpoena":          1.6,
    "whistleblower":     1.7,
    # Lower-impact terms
    "earnings":          1.1,
    "revenue":           1.0,
    "profit":            1.0,
    "loss":              1.1,
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RankedArticle:
    article_id: str
    url: str
    title: str
    source: str
    published_at: str
    final_score: float          # 0–1 composite
    relevance_score: float      # ping match component
    authority_score: float      # source tier component
    recency_score: float        # time-decay component
    keyword_boost: float        # backtested keyword multiplier
    matched_pings: list[str]    # ping topics that matched
    matched_keywords: list[str] # which boost keywords triggered
    rank: int = 0
    explanation: str = ""       # human-readable "why this ranked here"


@dataclass
class RankingResult:
    articles: list[RankedArticle]
    total_input: int
    above_threshold: int
    generated_at: str


# ---------------------------------------------------------------------------
# Ranker
# ---------------------------------------------------------------------------

class NewsRelevanceRanker:
    """
    Ranks news articles for a given user based on:
      1. Ping relevance (how well the article matches their active pings)
      2. Source authority (WSJ > unknown blog)
      3. Recency decay (fresh news scores higher)
      4. Keyword boost (historically market-moving terms score higher)

    Usage:
        ranker = NewsRelevanceRanker(user_id="user_1")
        articles = [...]  # list of dicts from NewsCrawler.search()
        result = ranker.rank(articles)
        for a in result.articles[:10]:
            print(f"{a.rank}. [{a.source}] {a.title}  score={a.final_score:.2f}")
            print(f"   Why: {a.explanation}")
    """

    def __init__(
        self,
        user_id: str = "default",
        pinger: Optional[TopicPinger] = None,
        min_score: float = 0.10,
        db_path: Path = Path("data/pings.db"),
    ):
        self.user_id = user_id
        self.pinger = pinger or TopicPinger(user_id=user_id, db_path=db_path)
        self.min_score = min_score

    # ------------------------------------------------------------------
    # Scoring components
    # ------------------------------------------------------------------

    def _authority_score(self, source: str) -> float:
        return SOURCE_AUTHORITY.get(source.lower(), SOURCE_AUTHORITY["unknown"])

    def _recency_score(self, published_at: str) -> float:
        """Exponential decay: score=1 at publish time, 0.5 at HALF_LIFE hours."""
        if not published_at:
            return 0.5
        try:
            pub = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            pub = pub.replace(tzinfo=None)  # strip tz for comparison
        except (ValueError, TypeError):
            return 0.5
        age_h = (datetime.utcnow() - pub).total_seconds() / 3600.0
        age_h = max(0.0, min(age_h, MAX_AGE_H))
        return math.exp(-math.log(2) * age_h / RECENCY_HALF_LIFE_H)

    def _keyword_boost(self, text: str) -> tuple[float, list[str]]:
        """
        Apply backtested keyword weight boosts.
        Returns (max_multiplier, list_of_matched_keywords).
        """
        t = text.lower()
        max_boost = 1.0
        matched = []
        for kw, weight in KEYWORD_BOOST_WEIGHTS.items():
            if kw in t:
                matched.append(kw)
                max_boost = max(max_boost, weight)
        return max_boost, matched

    def _ping_relevance(self, article: dict) -> tuple[float, list[str]]:
        """Match article against user's pings. Returns (score, ping_topics)."""
        matches = self.pinger.match_content(article, source_type="news")
        if not matches:
            return 0.0, []
        top_score = max(m.relevance_score for m in matches)
        # Bonus for multiple pings firing simultaneously
        multi_bonus = min(len(matches) * 0.05, 0.20)
        score = min(top_score + multi_bonus, 1.0)
        topics = [m.ping.topic for m in matches]
        return score, topics

    # ------------------------------------------------------------------
    # Main rank method
    # ------------------------------------------------------------------

    def rank(
        self,
        articles: list[dict],
        top_n: int = 0,
    ) -> RankingResult:
        """
        Rank a batch of article dicts.

        Args:
            articles: List of dicts from NewsCrawler.search()
            top_n: If > 0, return only the top N results

        Returns:
            RankingResult with sorted RankedArticle list
        """
        ranked = []
        for art in articles:
            text = " ".join(filter(None, [
                art.get("title", ""),
                art.get("summary", ""),
                art.get("full_text", "")[:2000],
            ]))

            authority   = self._authority_score(art.get("source", ""))
            recency     = self._recency_score(art.get("published_at", ""))
            kw_boost, matched_kw = self._keyword_boost(text)
            ping_rel, ping_topics = self._ping_relevance(art)

            # If no pings are set at all, fall back to keyword + authority
            active_pings = self.pinger.list_pings()
            if not active_pings:
                ping_rel = 0.5  # neutral when no pings configured

            # Composite score formula:
            #   base = authority * recency * kw_boost
            #   final = base * 0.4 + ping_relevance * 0.6
            # The 0.6 ping weight means user intent dominates
            base = authority * recency * kw_boost
            base = min(base, 1.0)
            final = base * 0.40 + ping_rel * 0.60

            if final < self.min_score:
                continue

            explanation = self._explain(
                authority, recency, kw_boost, matched_kw,
                ping_rel, ping_topics, final
            )

            ranked.append(RankedArticle(
                article_id=art.get("article_id", ""),
                url=art.get("url", ""),
                title=art.get("title", ""),
                source=art.get("source", ""),
                published_at=art.get("published_at", ""),
                final_score=round(final, 4),
                relevance_score=round(ping_rel, 4),
                authority_score=round(authority, 4),
                recency_score=round(recency, 4),
                keyword_boost=round(kw_boost, 4),
                matched_pings=ping_topics,
                matched_keywords=matched_kw,
                explanation=explanation,
            ))

        ranked.sort(key=lambda r: -r.final_score)
        if top_n > 0:
            ranked = ranked[:top_n]
        for i, r in enumerate(ranked):
            r.rank = i + 1

        return RankingResult(
            articles=ranked,
            total_input=len(articles),
            above_threshold=len(ranked),
            generated_at=datetime.utcnow().isoformat(),
        )

    def _explain(
        self, authority, recency, kw_boost, matched_kw,
        ping_rel, ping_topics, final
    ) -> str:
        parts = []
        if ping_topics:
            parts.append(f"matches your ping{'s' if len(ping_topics)>1 else ''}: "
                         f"{', '.join(repr(t) for t in ping_topics[:2])}")
        if matched_kw:
            parts.append(f"contains high-impact term{'s' if len(matched_kw)>1 else ''}: "
                         f"{', '.join(matched_kw[:3])}")
        if authority >= 0.90:
            parts.append("top-tier source")
        if recency > 0.85:
            parts.append("published recently")
        elif recency < 0.30:
            parts.append("older article")
        if not parts:
            parts.append(f"score={final:.2f}")
        return "; ".join(parts).capitalize() + "."

    def rank_for_ticker(self, ticker: str, articles: list[dict]) -> RankingResult:
        """Convenience: rank articles filtered to a specific ticker."""
        filtered = [
            a for a in articles
            if ticker.upper() in [t.upper() for t in a.get("tickers_mentioned", [])]
            or ticker.upper() in a.get("title", "").upper()
        ]
        return self.rank(filtered)


# ---------------------------------------------------------------------------
# Digest builder — groups top results by topic for a clean summary
# ---------------------------------------------------------------------------

def build_digest(result: RankingResult, max_items: int = 20) -> str:
    """
    Produce a plain-text digest of ranked articles.
    Format: ranked list with score, source, title, and explanation.
    No AI generation — raw content metadata only.
    """
    lines = [
        f"NEWS DIGEST — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        f"Showing top {min(max_items, len(result.articles))} of "
        f"{result.total_input} articles (threshold={result.above_threshold} passed)\n",
        "=" * 72,
    ]
    for art in result.articles[:max_items]:
        age_str = ""
        try:
            pub = datetime.fromisoformat(art.published_at.replace("Z", ""))
            age_h = (datetime.utcnow() - pub).total_seconds() / 3600
            age_str = f"{age_h:.0f}h ago"
        except Exception:
            pass

        lines.append(
            f"\n#{art.rank}  [{art.source.upper()}] {age_str}  "
            f"score={art.final_score:.2f}"
        )
        lines.append(f"    {art.title}")
        lines.append(f"    {art.url}")
        lines.append(f"    Why: {art.explanation}")
        if art.matched_keywords:
            lines.append(f"    Keywords: {', '.join(art.matched_keywords[:5])}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    # Demo: create sample pings, then rank a fake news batch
    pinger = TopicPinger(user_id="demo")
    pinger.ping("war between Iran and USA", priority="HIGH")
    pinger.ping("Federal Reserve rate hike", priority="HIGH")
    pinger.ping("NVDA", priority="CRITICAL", tickers=["NVDA"])

    ranker = NewsRelevanceRanker(user_id="demo", pinger=pinger)

    sample_articles = [
        {
            "article_id": "a1", "url": "https://reuters.com/1",
            "title": "Iran threatens oil disruption as US sanctions bite",
            "summary": "Iran warned of closing Strait of Hormuz",
            "full_text": "Tehran — Iran threatened Tuesday to close the Strait of Hormuz "
                         "after US imposed fresh sanctions on Iranian oil exports.",
            "source": "reuters", "published_at": datetime.utcnow().isoformat(),
            "tickers_mentioned": ["XOM", "CVX"],
        },
        {
            "article_id": "a2", "url": "https://wsj.com/2",
            "title": "Fed signals another rate hike amid persistent inflation",
            "summary": "Federal Reserve hints at 25bp rate increase",
            "full_text": "Washington — Federal Reserve Chair signaled a possible rate hike "
                         "at the next meeting if inflation remains elevated.",
            "source": "wsj", "published_at": datetime.utcnow().isoformat(),
            "tickers_mentioned": ["JPM", "BAC", "GS"],
        },
        {
            "article_id": "a3", "url": "https://cnbc.com/3",
            "title": "NVDA earnings beat estimates; guidance raised",
            "summary": "Nvidia reports record revenue, raises full-year guidance",
            "full_text": "Santa Clara — Nvidia reported quarterly earnings that beat "
                         "Wall Street estimates by 15%, raising annual guidance.",
            "source": "cnbc", "published_at": datetime.utcnow().isoformat(),
            "tickers_mentioned": ["NVDA"],
        },
        {
            "article_id": "a4", "url": "https://marketwatch.com/4",
            "title": "Local restaurant chain expands to third location",
            "summary": "A small restaurant chain opens in Ohio",
            "full_text": "The restaurant opened its third location this weekend.",
            "source": "marketwatch", "published_at": datetime.utcnow().isoformat(),
            "tickers_mentioned": [],
        },
    ]

    result = ranker.rank(sample_articles)
    print(build_digest(result))
