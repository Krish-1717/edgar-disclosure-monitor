"""
edgar/nlp_scorer.py -- NLP materiality scoring for EDGAR filings
Day 9 Commit 1: keyword-weighted count + sentiment delta + structural edit ratio.
"""
from __future__ import annotations
import re
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ââ Materiality keyword weights ââââââââââââââââââââââââââââââââââââââââââââââââ

_KEYWORD_WEIGHTS: Dict[str, float] = {
    # High materiality
    "restatement": 3.0, "going concern": 3.0, "material weakness": 3.0,
    "fraud": 3.0, "litigation": 2.5, "regulatory action": 2.5,
    "impairment": 2.0, "goodwill impairment": 2.5, "bankruptcy": 3.0,
    "default": 2.5, "covenant violation": 2.5, "sec investigation": 3.0,
    # Medium materiality
    "acquisition": 1.5, "divestiture": 1.5, "restructuring": 1.5,
    "workforce reduction": 1.5, "layoff": 1.5, "ceo departure": 2.0,
    "leadership change": 1.5, "guidance reduction": 2.0,
    "revenue decline": 1.5, "margin compression": 1.5,
    # Lower materiality
    "dividend": 0.5, "share repurchase": 0.5, "product launch": 0.5,
    "expansion": 0.5, "partnership": 0.5,
}

# ââ Simple lexicon-based sentiment ââââââââââââââââââââââââââââââââââââââââââââ

_POSITIVE = {
    "improvement", "growth", "increase", "exceeds", "strong",
    "record", "gain", "profitable", "positive", "favorable",
    "ahead", "better", "robust", "solid", "expand",
}
_NEGATIVE = {
    "decrease", "decline", "loss", "below", "weak", "poor",
    "unfavorable", "impairment", "concern", "risk", "uncertainty",
    "deficit", "violation", "litigation", "adverse", "delay",
}
_NEGATORS = {"not", "no", "never", "neither", "nor", "without", "lack"}


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z]+(?:'[a-z]+)?", text.lower())


def _sentiment_score(text: str) -> float:
    """Lexicon-based sentiment in [-1, +1] with simple negation handling."""
    tokens = _tokenize(text)
    score = 0.0
    n = len(tokens)
    for i, tok in enumerate(tokens):
        window = set(tokens[max(0, i-3):i])
        negated = bool(window & _NEGATORS)
        if tok in _POSITIVE:
            score += -1.0 if negated else 1.0
        elif tok in _NEGATIVE:
            score += 1.0 if negated else -1.0
    return math.tanh(score / max(1, n / 50))


def _keyword_density(text: str, max_score: float = 10.0) -> Tuple[float, List[str]]:
    """Weighted keyword count, normalised to [0,1]."""
    text_lower = text.lower()
    total = 0.0
    found: List[str] = []
    for kw, w in _KEYWORD_WEIGHTS.items():
        count = text_lower.count(kw)
        if count:
            total += w * count
            found.append(kw)
    return min(total / max_score, 1.0), found


def _edit_ratio(old: str, new: str) -> float:
    """Word-level edit ratio â [0, 1]: fraction of words that changed."""
    old_words = set(_tokenize(old))
    new_words = set(_tokenize(new))
    if not old_words and not new_words:
        return 0.0
    added = new_words - old_words
    removed = old_words - new_words
    union = old_words | new_words
    return len(added | removed) / len(union)


# ââ Scoring result ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

@dataclass
class MaterialityResult:
    materiality: float              # composite score â [0, 1]
    keyword_score: float            # keyword-density component
    sentiment_delta: float          # |Îsentiment| component
    structural_change: float        # edit-ratio component
    keywords_found: List[str] = field(default_factory=list)
    old_sentiment: float = 0.0
    new_sentiment: float = 0.0

    def is_material(self, threshold: float = 0.35) -> bool:
        return self.materiality >= threshold

    def summary(self) -> str:
        flag = "MATERIAL" if self.is_material() else "not material"
        return (
            f"{flag}  materiality={self.materiality:.3f}  "
            f"(kw={self.keyword_score:.3f}  "
            f"snt_Î={self.sentiment_delta:.3f}  "
            f"edit={self.structural_change:.3f})"
        )


# ââ Main scorer âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

class NLPScorer:
    """Score the materiality of changes between two EDGAR filing sections."""

    def __init__(
        self,
        kw_weight: float = 0.5,
        snt_weight: float = 0.25,
        edit_weight: float = 0.25,
    ):
        assert abs(kw_weight + snt_weight + edit_weight - 1.0) < 1e-6
        self.kw_weight = kw_weight
        self.snt_weight = snt_weight
        self.edit_weight = edit_weight

    def score(self, old_text: str, new_text: str) -> MaterialityResult:
        kw_score, keywords = _keyword_density(new_text)
        old_snt = _sentiment_score(old_text)
        new_snt = _sentiment_score(new_text)
        snt_delta = min(abs(new_snt - old_snt) / 2.0, 1.0)
        edit = _edit_ratio(old_text, new_text)
        composite = (
            self.kw_weight * kw_score
            + self.snt_weight * snt_delta
            + self.edit_weight * edit
        )
        return MaterialityResult(
            materiality=min(composite, 1.0),
            keyword_score=kw_score,
            sentiment_delta=snt_delta,
            structural_change=edit,
            keywords_found=keywords,
            old_sentiment=old_snt,
            new_sentiment=new_snt,
        )

    def score_sections(
        self, sections: Dict[str, Tuple[str, str]]
    ) -> Dict[str, MaterialityResult]:
        """Score multiple sections. sections = {name: (old_text, new_text)}."""
        return {name: self.score(old, new) for name, (old, new) in sections.items()}
