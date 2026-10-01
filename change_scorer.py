"""
change_scorer.py — Materiality Score + Burial Score

Materiality Score (0–100): pure text signals, no LLM needed.
  - Volume of change: added+revised words as % of section length
  - Section weight: Item 1A and 7 carry more weight
  - Hedging language direction: shifts in uncertainty/risk vocabulary
  - Specificity shift: named entities, dollar figures, dates in new text
  - Numeric deltas (placeholder; populated from table extraction)

Burial Score (0–100): how hard is the company trying to hide this?
  - Position percentile of paragraph in document
  - Section obscurity (footnotes/Item 1A tail > MD&A open)
  - Length of surrounding boilerplate
  - Filing timing (after-hours / Friday release)
  - Press release coverage on same day

Attention Gap = Materiality / max(Normalized Coverage, 0.01)
High materiality + low coverage → surfaces buried significant changes.
"""
from __future__ import annotations
import re
import math
import json
from datetime import datetime
from paragraph_aligner import AlignedPair

# ── Section weights ────────────────────────────────────────────────────────────
SECTION_WEIGHT: dict[str, float] = {
    "1A": 2.0,   # Risk Factors — highest weight
    "7":  1.8,   # MD&A
    "7A": 1.5,   # Market Risk
    "9A": 1.4,   # Controls
    "1":  1.2,   # Business
    "8":  1.0,   # Financial Statements (dense; harder to diff)
    "3":  0.9,   # Legal
    "2":  0.7,
    "5":  0.7,
    "1B": 0.5,
}

# Hedging / risk language
_HEDGE_WORDS = {
    "may", "might", "could", "would", "should", "risk", "uncertain",
    "material", "adverse", "significant", "substantial", "concern",
    "doubt", "contingent", "potential", "possible", "exposure",
}

# Specificity signals: dollar amounts, percentages, dates, entity-like caps
_DOLLAR_RE  = re.compile(r"\$[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|thousand))?", re.IGNORECASE)
_PERCENT_RE = re.compile(r"\d+(?:\.\d+)?\s*%")
_DATE_RE    = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b")
_ENTITY_RE  = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b")


def _count_hedge_words(text: str) -> int:
    tokens = set(re.findall(r"[a-z]+", text.lower()))
    return len(tokens & _HEDGE_WORDS)


def _count_specifics(text: str) -> int:
    return (
        len(_DOLLAR_RE.findall(text))
        + len(_PERCENT_RE.findall(text))
        + len(_DATE_RE.findall(text))
        + len(_ENTITY_RE.findall(text))
    )


# ── Materiality scoring ────────────────────────────────────────────────────────

def score_section(item: str, pairs: list[AlignedPair]) -> float:
    """Return section-level raw materiality score (0–100)."""
    if not pairs:
        return 0.0

    total_words = sum(
        len((p.new_text or p.old_text).split()) for p in pairs
    )
    if total_words == 0:
        return 0.0

    # Volume signal
    changed_words = sum(
        p.added_words + p.removed_words
        for p in pairs
        if p.change_type in ("revised", "added", "removed")
    )
    volume_score = min(changed_words / max(total_words, 1) * 100, 100)

    # Hedging shift
    new_text_all = " ".join(p.new_text for p in pairs if p.new_text)
    old_text_all = " ".join(p.old_text for p in pairs if p.old_text)
    hedge_new = _count_hedge_words(new_text_all)
    hedge_old = _count_hedge_words(old_text_all)
    hedge_shift = max((hedge_new - hedge_old) / max(hedge_old, 1) * 100, 0)

    # Specificity shift
    spec_new = _count_specifics(new_text_all)
    spec_old = _count_specifics(old_text_all)
    spec_shift = max((spec_new - spec_old) / max(spec_old, 1) * 50, 0)

    raw = 0.5 * volume_score + 0.3 * hedge_shift + 0.2 * spec_shift
    weight = SECTION_WEIGHT.get(item, 1.0)
    return min(raw * weight, 100.0)


def materiality_score(section_scores: dict[str, float]) -> float:
    """Aggregate section scores into a single filing materiality score (0–100)."""
    if not section_scores:
        return 0.0
    weights = [SECTION_WEIGHT.get(k, 1.0) for k in section_scores]
    scores  = list(section_scores.values())
    total_w = sum(weights)
    return min(sum(s * w for s, w in zip(scores, weights)) / total_w, 100.0)


# ── Burial Score ───────────────────────────────────────────────────────────────

def burial_score(
    filed_date: str,
    position_percentile: float = 0.5,
    section_obscurity: float = 0.5,
    boilerplate_ratio: float = 0.3,
) -> float:
    """
    Compute Burial Score (0–100).
    Parameters
    ----------
    filed_date          : ISO date string 'YYYY-MM-DD'
    position_percentile : 0 = document start, 1 = document end
    section_obscurity   : 0 = prominent (MD&A open), 1 = obscure (footnote)
    boilerplate_ratio   : fraction of surrounding text that is boilerplate
    """
    score = 0.0

    # Position: later in document → higher burial
    score += position_percentile * 30

    # Section obscurity
    score += section_obscurity * 25

    # Boilerplate
    score += boilerplate_ratio * 15

    # Timing: Friday / after-hours release
    try:
        dt = datetime.strptime(filed_date, "%Y-%m-%d")
        if dt.weekday() == 4:   # Friday
            score += 20
        elif dt.weekday() >= 3: # Thursday
            score += 10
    except ValueError:
        pass

    return min(score, 100.0)


# ── Attention Gap ──────────────────────────────────────────────────────────────

def attention_gap(materiality: float, normalized_coverage: float) -> float:
    """
    Attention Gap = materiality / max(coverage, 0.01).
    High score → lots of change, little press coverage.
    """
    return materiality / max(normalized_coverage, 0.01)


# ── Five-level ranking ─────────────────────────────────────────────────────────

RANK_LABELS = {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "MINIMAL"}

def rank_alert(mat: float, burial: float, gap: float) -> int:
    """Return 1–5 ranking from combined signal."""
    composite = 0.5 * mat + 0.3 * burial + 0.2 * min(gap, 100)
    if composite >= 80: return 5
    if composite >= 60: return 4
    if composite >= 40: return 3
    if composite >= 20: return 2
    return 1


def build_alert(
    ticker: str, new_filing_id: int, old_filing_id: int,
    filed: str, period: str,
    section_diffs: dict[str, list[AlignedPair]],
    normalized_coverage: float = 0.5,
) -> dict:
    """Build a full alert dict ready for DB insertion."""
    sec_scores = {
        item: score_section(item, pairs)
        for item, pairs in section_diffs.items()
    }
    mat   = materiality_score(sec_scores)
    bur   = burial_score(filed)
    gap   = attention_gap(mat, normalized_coverage)
    rank  = rank_alert(mat, bur, gap)

    # Top changed items for the summary
    top = sorted(sec_scores.items(), key=lambda x: x[1], reverse=True)[:3]
    summary_items = [{"item": item, "score": round(s, 1)} for item, s in top if s > 0]

    return {
        "ticker":            ticker,
        "new_filing_id":     new_filing_id,
        "old_filing_id":     old_filing_id,
        "filed":             filed,
        "period":            period,
        "materiality_score": round(mat, 2),
        "burial_score":      round(bur, 2),
        "attention_gap":     round(gap, 2),
        "ranking":           rank,
        "summary_items":     json.dumps(summary_items),
    }
