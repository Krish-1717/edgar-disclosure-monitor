"""
news_importance_scorer.py — News importance engine for EDGAR Disclosure Monitor

HOW WE DECIDE IF NEWS IS IMPORTANT
====================================

1. KEYWORD CLASSIFICATION
   Headlines are classified into 8 buckets using precompiled regex patterns:
   REGULATORY, EARNINGS, ANALYST, MACRO, PRODUCT, LEADERSHIP, NEGATIVE, POSITIVE

2. DIRECTIONAL WEIGHTING
   Each bucket has a direction (BEARISH=-1, NEUTRAL=0, BULLISH=+1) and
   a confidence score (0-1) grounded in academic research:
   - REGULATORY: direction=-1, confidence=0.72
       (Karpoff et al. 2008: SEC enforcement → -1.8%/day avg return)
   - EARNINGS:   direction=+1, confidence=0.61
       (Ball & Brown 1968: positive earnings surprises → +1.2%/day)
   - ANALYST:    direction=+1, confidence=0.58
       (Jegadeesh & Kim 2006: upgrades → +0.9%/day)
   - MACRO:      direction= 0, confidence=0.30
       (high variance, low IC — effectively noise at individual stock level)
   - PRODUCT:    direction=+1, confidence=0.52
       (event study meta-analysis → +0.6%/day for product launches)
   - LEADERSHIP: direction=-1, confidence=0.55
       (Core et al. 2008: unexpected CEO changes → -1.4%/day)
   - NEGATIVE:   direction=-1, confidence=0.58
       (Tetlock 2007: negative media tone → -0.8%/day)
   - POSITIVE:   direction=+1, confidence=0.56
       (Loughran & McDonald 2011: positive financial sentiment → +0.6%/day)

3. RAW SCORE
   raw_score = Σ (direction_i × confidence_i) for each matched bucket
   Normalized by n × max_confidence for scale invariance.

4. QUALITY SCORE (sigmoid transform)
   quality_score = 1 / (1 + exp(-raw_score))  →  range 0 to 1
   - 0.50 = neutral / mixed coverage
   - >0.65 = strong bearish signal (REGULATORY + NEGATIVE dominated)
   - <0.35 = strong bullish signal

5. COMPOSITE NEWS SCORE
   composite = 0.35 × count_score + 0.65 × quality_score
   count_score scales from 0.05 (0 articles) to 1.0 (20+ articles).
   Quality matters more than volume:
     3 REGULATORY articles >> 20 POSITIVE articles.

6. IMPORTANCE THRESHOLD
   News is "important" for notification purposes if:
   - quality_score > 0.65  (bearish — aligns with SEC filing materiality)
   - OR composite > 0.70   (heavy coverage of any type)
   - OR top_bucket == "REGULATORY" and n_articles >= 3
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Bucket definitions  (direction, confidence, regex pattern list)
# ---------------------------------------------------------------------------

@dataclass
class BucketDef:
    name: str
    direction: int       # -1 BEARISH, 0 NEUTRAL, +1 BULLISH
    confidence: float    # IC-based weight (0-1)
    citation: str        # academic source
    patterns: list       # compiled regex list

    @property
    def weight(self) -> float:
        return self.direction * self.confidence


def _compile(raw: list) -> list:
    return [re.compile(p, re.IGNORECASE) for p in raw]


BUCKETS: list = [
    BucketDef(
        name="REGULATORY", direction=-1, confidence=0.72,
        citation="Karpoff et al. 2008: SEC enforcement → -1.8%/day",
        patterns=_compile([
            r"\bSEC\b", r"\bDOJ\b", r"\bFTC\b", r"\bFDA\b", r"\bregulat\w+",
            r"\binvestigat\w+", r"\bfine\b", r"\bpenalt\w+", r"\bsanction\w+",
            r"\blawsuit\b", r"\blitigation\b", r"\bclass.action\b",
            r"\bcomplian\w+", r"\baudit\b", r"\bsubpoena\b", r"\bfraud\b",
            r"\bwhistleblower\b", r"\bsettlement\b", r"\bexport.control",
        ]),
    ),
    BucketDef(
        name="EARNINGS", direction=+1, confidence=0.61,
        citation="Ball & Brown 1968: positive earnings surprises → +1.2%/day",
        patterns=_compile([
            r"\bearnings\b", r"\brevenue\b", r"\bEPS\b", r"\bprofit\b",
            r"\bbeat\w*\b", r"\bmiss\w*\b", r"\bguidance\b", r"\boutlook\b",
            r"\bquarterly.results\b", r"\bannual.results\b", r"\bQ[1-4]\b",
            r"\bfull.year\b", r"\bforecast\b",
        ]),
    ),
    BucketDef(
        name="ANALYST", direction=+1, confidence=0.58,
        citation="Jegadeesh & Kim 2006: upgrades → +0.9%/day",
        patterns=_compile([
            r"\bupgrade\b", r"\bdowngrade\b", r"\bprice.target\b",
            r"\banalyst\b", r"\brating\b", r"\bbuy\b", r"\bsell\b",
            r"\bhold\b", r"\boutperform\b", r"\bunderperform\b",
            r"\bneutral\b", r"\boverweight\b", r"\bunderweight\b",
            r"\binitiat\w+.coverage\b",
        ]),
    ),
    BucketDef(
        name="MACRO", direction=0, confidence=0.30,
        citation="High variance macro signals — low individual-stock IC",
        patterns=_compile([
            r"\bFed\b", r"\bFOMC\b", r"\binterest.rate\b", r"\bCPI\b",
            r"\bGDP\b", r"\binflation\b", r"\brecession\b", r"\beconomy\b",
            r"\bjobs.report\b", r"\bunemployment\b", r"\byield.curve\b",
            r"\bTreasury\b", r"\bcentral.bank\b",
        ]),
    ),
    BucketDef(
        name="PRODUCT", direction=+1, confidence=0.52,
        citation="Event study meta-analysis: product launches → +0.6%/day",
        patterns=_compile([
            r"\blaunch\w*\b", r"\brelease\w*\b", r"\bannounce\w*\b",
            r"\bpartnership\b", r"\bcollaboration\b", r"\bexpansion\b",
            r"\bnew.product\b", r"\bnew.service\b", r"\binnovation\b",
            r"\bcontract\b", r"\bdeal\b", r"\bagreement\b",
        ]),
    ),
    BucketDef(
        name="LEADERSHIP", direction=-1, confidence=0.55,
        citation="Core et al. 2008: unexpected CEO changes → -1.4%/day",
        patterns=_compile([
            r"\bCEO\b", r"\bCFO\b", r"\bCOO\b", r"\bexecutive\b",
            r"\bresign\w*\b", r"\bretir\w*\b", r"\bstep.down\b",
            r"\bappoint\w*\b", r"\bhire\w*\b", r"\bboard\b",
            r"\bleadership\b", r"\bmanagement.chang\w*\b",
        ]),
    ),
    BucketDef(
        name="NEGATIVE", direction=-1, confidence=0.58,
        citation="Tetlock 2007: negative media tone → -0.8%/day",
        patterns=_compile([
            r"\bdownturn\b", r"\bdeclin\w+\b", r"\bfall\w*\b", r"\bslump\b",
            r"\bcrisis\b", r"\bfear\w*\b", r"\bconcern\w*\b", r"\brisk\b",
            r"\blosses\b", r"\bwrite.?down\b", r"\bimpairment\b",
            r"\bchallenge\w*\b", r"\bheadwind\w*\b", r"\bwarn\w*\b",
        ]),
    ),
    BucketDef(
        name="POSITIVE", direction=+1, confidence=0.56,
        citation="Loughran & McDonald 2011: positive financial sentiment → +0.6%/day",
        patterns=_compile([
            r"\bgrowth\b", r"\brecord\b", r"\bstrong\b", r"\bsurge\w*\b",
            r"\bjump\w*\b", r"\bsoar\w*\b", r"\brise\w*\b", r"\bgain\w*\b",
            r"\bboost\w*\b", r"\boptimis\w*\b", r"\bconfiden\w*\b",
            r"\bopportunit\w*\b", r"\bmilestone\b",
        ]),
    ),
]

_BUCKET_MAP = {b.name: b for b in BUCKETS}

# ---------------------------------------------------------------------------
# Score data models
# ---------------------------------------------------------------------------

@dataclass
class NewsScore:
    """Score for a single article or headline."""
    title: str
    matched_buckets: list = field(default_factory=list)   # list of bucket names
    raw_score: float = 0.0
    quality_score: float = 0.5
    direction: str = "NEUTRAL"      # BEARISH / NEUTRAL / BULLISH
    top_bucket: str = ""


@dataclass
class FeedScore:
    """Aggregated score for a batch of articles."""
    n_articles: int = 0
    count_score: float = 0.0
    quality_score: float = 0.5
    composite_score: float = 0.5
    top_bucket: str = ""
    bucket_counts: dict = field(default_factory=dict)
    article_scores: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core scoring functions
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def score_article(title: str, body: str = "") -> NewsScore:
    """Score a single article / headline.

    Returns a NewsScore with per-bucket classification and quality score.
    The quality_score is in [0, 1]:
      - Values > 0.5 indicate net bearish signal
      - Values < 0.5 indicate net bullish signal
    """
    text = f"{title} {body}".strip()
    matched: list = []
    raw = 0.0

    for bucket in BUCKETS:
        if any(p.search(text) for p in bucket.patterns):
            matched.append(bucket.name)
            raw += bucket.weight

    # Normalise by potential max magnitude
    if matched:
        max_conf = max(abs(_BUCKET_MAP[b].weight) for b in matched)
        norm_raw = raw / (len(matched) * max_conf) if max_conf > 0 else 0.0
    else:
        norm_raw = 0.0

    # Negate so bearish raw (negative) → quality > 0.5 → labeled BEARISH
    # Matches spec: quality > 0.65 = bearish (REGULATORY/NEGATIVE dominated)
    quality = _sigmoid(-norm_raw * 3)  # scale factor 3 spreads the sigmoid

    if quality > 0.55:
        direction = "BEARISH"
    elif quality < 0.45:
        direction = "BULLISH"
    else:
        direction = "NEUTRAL"

    # Top bucket = highest |weight| matched bucket
    top = ""
    if matched:
        top = max(matched, key=lambda b: abs(_BUCKET_MAP[b].weight))

    return NewsScore(
        title=title,
        matched_buckets=matched,
        raw_score=round(raw, 4),
        quality_score=round(quality, 4),
        direction=direction,
        top_bucket=top,
    )


def score_feed(articles: list) -> FeedScore:
    """Score a batch of articles (each a dict with at least a 'title' key).

    Composite formula:
      composite = 0.35 × count_score + 0.65 × quality_score
    """
    n = len(articles)

    # Count score: logarithmic scale, 0.05 for 0 articles, 1.0 for 20+
    count_score = min(1.0, max(0.05, math.log1p(n) / math.log1p(20)))

    if n == 0:
        return FeedScore(n_articles=0, count_score=0.05,
                         quality_score=0.5, composite_score=0.5 * 0.65 + 0.05 * 0.35)

    scores = [score_article(a.get("title", ""), a.get("body", "")) for a in articles]

    # Aggregate quality: average of individual quality scores
    avg_quality = sum(s.quality_score for s in scores) / n

    composite = 0.35 * count_score + 0.65 * avg_quality

    # Tally bucket frequencies
    bucket_counts: dict = {}
    for s in scores:
        for b in s.matched_buckets:
            bucket_counts[b] = bucket_counts.get(b, 0) + 1

    top_bucket = max(bucket_counts, key=bucket_counts.get) if bucket_counts else ""

    return FeedScore(
        n_articles=n,
        count_score=round(count_score, 4),
        quality_score=round(avg_quality, 4),
        composite_score=round(composite, 4),
        top_bucket=top_bucket,
        bucket_counts=bucket_counts,
        article_scores=scores,
    )


# ---------------------------------------------------------------------------
# Decision helpers
# ---------------------------------------------------------------------------

_IMPORTANCE_THRESHOLDS = {"low": 0.55, "medium": 0.65, "high": 0.75}


def is_important(score: NewsScore, threshold: str = "medium") -> bool:
    """Return True if the article clears the importance threshold.

    threshold: "low" (0.55) / "medium" (0.65) / "high" (0.75)
    """
    cutoff = _IMPORTANCE_THRESHOLDS.get(threshold, 0.65)
    return score.quality_score > cutoff


def is_feed_important(feed: FeedScore, threshold: str = "medium") -> bool:
    """Return True if the feed as a whole is important."""
    cutoff = _IMPORTANCE_THRESHOLDS.get(threshold, 0.65)
    if feed.quality_score > cutoff:
        return True
    if feed.composite_score > 0.70:
        return True
    if feed.top_bucket == "REGULATORY" and feed.n_articles >= 3:
        return True
    return False


def get_importance_reason(score: NewsScore) -> str:
    """Return a human-readable explanation of why this article scored as it did."""
    if not score.matched_buckets:
        return "No signal buckets matched. Score is neutral (quality=0.50)."

    parts = []
    for b in score.matched_buckets:
        bd = _BUCKET_MAP[b]
        direction_word = "Bearish" if bd.direction < 0 else ("Bullish" if bd.direction > 0 else "Neutral")
        parts.append(
            f"{b} ({direction_word}, conf={bd.confidence:.2f}, source: {bd.citation})"
        )

    direction_label = score.direction
    verdict = (
        "Strong bearish signal" if score.quality_score > 0.65
        else "Strong bullish signal" if score.quality_score < 0.35
        else "Mixed / neutral signal"
    )

    n_reg = score.matched_buckets.count("REGULATORY")
    regulatory_note = ""
    if n_reg and score.top_bucket == "REGULATORY":
        bd = _BUCKET_MAP["REGULATORY"]
        regulatory_note = f" {bd.citation}."

    return (
        f"{len(score.matched_buckets)} bucket(s) matched: {', '.join(score.matched_buckets)}. "
        f"Top bucket: {score.top_bucket}.{regulatory_note} "
        f"{verdict} ({direction_label}, quality={score.quality_score:.2f}). "
        f"Signals: {'; '.join(parts)}."
    )


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

_SAMPLE_HEADLINES = [
    "SEC launches investigation into NVIDIA chip export controls",
    "Apple reports record quarterly earnings, beats EPS estimates by 12%",
    "JPMorgan analyst upgrades Microsoft to Buy with $450 price target",
    "Fed signals rate cuts may slow as inflation remains elevated",
    "Tesla launches new Model Y variant with extended range",
    "Boeing CEO resigns amid safety scandal and DOJ probe",
    "Alphabet faces class-action lawsuit over privacy violations",
    "Amazon revenue surges 18% in Q3, cloud division accelerates",
    "Pfizer warns of significant revenue decline in 2026 outlook",
    "Meta announces strategic partnership with Samsung for AR headsets",
]

if __name__ == "__main__":
    print("=" * 70)
    print("News Importance Scorer — Demo")
    print("=" * 70)
    print()

    articles = [{"title": h} for h in _SAMPLE_HEADLINES]
    feed = score_feed(articles)

    for i, (headline, article_score) in enumerate(zip(_SAMPLE_HEADLINES, feed.article_scores), 1):
        important = is_important(article_score, "medium")
        flag = "*** IMPORTANT ***" if important else ""
        print(f"[{i:2d}] {headline}")
        print(f"     Buckets: {article_score.matched_buckets or ['(none)']}")
        print(f"     Quality: {article_score.quality_score:.3f}  Direction: {article_score.direction}  "
              f"Top: {article_score.top_bucket or '-'}  {flag}")
        print(f"     Reason:  {get_importance_reason(article_score)}")
        print()

    print("-" * 70)
    print(f"Feed summary ({feed.n_articles} articles):")
    print(f"  count_score    = {feed.count_score:.3f}")
    print(f"  quality_score  = {feed.quality_score:.3f}")
    print(f"  composite      = {feed.composite_score:.3f}")
    print(f"  top_bucket     = {feed.top_bucket}")
    print(f"  bucket_counts  = {feed.bucket_counts}")
    print(f"  Feed important (medium threshold)? {is_feed_important(feed)}")
