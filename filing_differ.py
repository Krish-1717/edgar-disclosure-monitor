"""
filing_differ.py — Core diff engine: cross-examine two ParsedFiling objects.

Provides:
    ItemDiff     — per-item diff results
    FilingDiff   — full filing diff
    diff_filings(old, new) -> FilingDiff

Usage:
    python filing_differ.py  # demo
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional

from filing_parser import ParsedFiling, FilingItem

# ── Hedging word sets ───────────────────────────────────────────────────────────

_SOFT_WORDS = re.compile(
    r"\b(may|might|could|target|approximately|subject\s+to|expected?\s+to|"
    r"intend|anticipat|likely|possible|potential|estimate|around|about|"
    r"roughly|projected?)\b",
    re.I,
)
_HARD_WORDS = re.compile(
    r"\b(will|expect|commit|guarantee|certain|definite|assure|pledg|"
    r"promise|shall)\b",
    re.I,
)

# Number patterns for change detection
_NUMBER_RE = re.compile(
    r"(\$[\d,]+(?:\.\d+)?\s*(?:million|billion|trillion|[MBKT])?|"
    r"[\d,]+(?:\.\d+)?\s*(?:million|billion|trillion)\s*dollars?|"
    r"[\d,]+(?:\.\d+)?\s*%)",
    re.I,
)


# ── Dataclasses ─────────────────────────────────────────────────────────────────

@dataclass
class ItemDiff:
    item_num: str
    word_delta: float          # (new - old) / old word count
    similarity: float          # SequenceMatcher ratio
    added_sentences: list[str] = field(default_factory=list)
    removed_sentences: list[str] = field(default_factory=list)
    hedging_shift: float = 0.0  # positive = more hedged
    number_changes: list[dict] = field(default_factory=list)
    materiality_score: float = 0.0  # 0-1

    def __post_init__(self):
        if not self.materiality_score:
            self._compute_materiality()

    def _compute_materiality(self):
        score = (
            0.5 * abs(self.word_delta)
            + 0.3 * (1.0 - self.similarity)
            + 0.2 * abs(self.hedging_shift)
        )
        self.materiality_score = min(1.0, max(0.0, score))


@dataclass
class FilingDiff:
    ticker: str
    old_filing: ParsedFiling
    new_filing: ParsedFiling
    item_diffs: dict[str, ItemDiff] = field(default_factory=dict)
    overall_materiality: float = 0.0
    top_changed_items: list[str] = field(default_factory=list)

    def get_top_changes(self, n: int = 5) -> list[ItemDiff]:
        """Return top n ItemDiff objects sorted by materiality_score descending."""
        sorted_diffs = sorted(
            self.item_diffs.values(),
            key=lambda d: d.materiality_score,
            reverse=True,
        )
        return sorted_diffs[:n]


# ── Sentence utilities ──────────────────────────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    """Simple sentence splitter."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if len(s.strip()) > 20]


def _find_new_sentences(old_sents: list[str], new_sents: list[str], threshold: float = 0.75) -> list[str]:
    """Return sentences in new that don't have a close match in old."""
    added = []
    for ns in new_sents:
        best = max(
            (SequenceMatcher(None, ns, os, autojunk=False).ratio() for os in old_sents),
            default=0.0,
        )
        if best < threshold:
            added.append(ns)
    return added


def _count_hedge_words(text: str) -> tuple[int, int]:
    """Return (soft_count, hard_count)."""
    words = text.split()
    total = max(len(words), 1)
    soft = len(_SOFT_WORDS.findall(text))
    hard = len(_HARD_WORDS.findall(text))
    return soft, hard


def _extract_numbers(text: str) -> list[str]:
    return _NUMBER_RE.findall(text)


def _find_number_changes(old_text: str, new_text: str) -> list[dict]:
    """Find changed numeric values between filings."""
    old_nums = _extract_numbers(old_text)
    new_nums = _extract_numbers(new_text)
    changes = []

    # Simple approach: pair up numbers that appear at similar positions
    old_set = set(n.replace(",", "").lower() for n in old_nums)
    new_set = set(n.replace(",", "").lower() for n in new_nums)

    removed = old_set - new_set
    added = new_set - old_set

    # Try to pair removed with added numbers for context
    for old_val in list(removed)[:10]:
        for new_val in list(added)[:10]:
            changes.append({"old_val": old_val, "new_val": new_val, "context": ""})
            added.discard(new_val)
            break

    return changes[:20]  # cap at 20 pairs


# ── Core diff function ──────────────────────────────────────────────────────────

def _diff_item_pair(old_item: FilingItem, new_item: FilingItem) -> ItemDiff:
    """Compute ItemDiff between two versions of the same item."""
    old_words = max(old_item.word_count, 1)
    new_words = new_item.word_count
    word_delta = (new_words - old_words) / old_words

    # Similarity on full text (trimmed to avoid huge memory usage)
    old_text = old_item.text[:50_000]
    new_text = new_item.text[:50_000]
    similarity = SequenceMatcher(None, old_text, new_text, autojunk=False).ratio()

    # Sentence-level diff
    old_sents = _split_sentences(old_item.text)
    new_sents = _split_sentences(new_item.text)
    added_sents = _find_new_sentences(old_sents, new_sents)
    removed_sents = _find_new_sentences(new_sents, old_sents)

    # Hedging shift
    old_soft, old_hard = _count_hedge_words(old_item.text)
    new_soft, new_hard = _count_hedge_words(new_item.text)
    denom = max(old_words, 1)
    hedging_shift = (
        (new_soft - old_soft) / denom
        - (new_hard - old_hard) / denom
    )

    # Number changes
    number_changes = _find_number_changes(old_item.text, new_item.text)

    diff = ItemDiff(
        item_num=new_item.item_num,
        word_delta=word_delta,
        similarity=similarity,
        added_sentences=added_sents[:20],
        removed_sentences=removed_sents[:20],
        hedging_shift=hedging_shift,
        number_changes=number_changes,
        materiality_score=0.0,  # will be computed in __post_init__
    )
    diff._compute_materiality()
    return diff


def diff_filings(old: ParsedFiling, new: ParsedFiling) -> FilingDiff:
    """Cross-examine two ParsedFiling objects and return a FilingDiff."""
    old_items = {item.item_num: item for item in old.items}
    new_items = {item.item_num: item for item in new.items}

    item_diffs: dict[str, ItemDiff] = {}

    # Diff shared items
    for num, new_item in new_items.items():
        if num in old_items:
            item_diffs[num] = _diff_item_pair(old_items[num], new_item)
        else:
            # New item added — treat as entirely new text
            fake_old = FilingItem(item_num=num, title=new_item.title, text="", word_count=1)
            item_diffs[num] = _diff_item_pair(fake_old, new_item)

    # Compute overall materiality as weighted average of item materiality scores
    if item_diffs:
        scores = [d.materiality_score for d in item_diffs.values()]
        overall = sum(scores) / len(scores)
    else:
        overall = 0.0

    top_items = [
        d.item_num
        for d in sorted(item_diffs.values(), key=lambda x: x.materiality_score, reverse=True)[:5]
    ]

    return FilingDiff(
        ticker=new.ticker,
        old_filing=old,
        new_filing=new,
        item_diffs=item_diffs,
        overall_materiality=round(overall, 4),
        top_changed_items=top_items,
    )


if __name__ == "__main__":
    from filing_fetcher import FilingFetcher
    from filing_parser import parse_filing

    print("Demo: diffing AAPL 10-K filings...")
    fetcher = FilingFetcher()
    old_meta, new_meta = fetcher.get_two_most_recent("AAPL", "10-K")
    old_parsed = parse_filing(old_meta)
    new_parsed = parse_filing(new_meta)
    diff = diff_filings(old_parsed, new_parsed)
    print(f"  Overall materiality: {diff.overall_materiality:.3f}")
    print(f"  Top changed items: {diff.top_changed_items}")
    for item_diff in diff.get_top_changes(3):
        print(f"    Item {item_diff.item_num}: materiality={item_diff.materiality_score:.3f} "
              f"sim={item_diff.similarity:.3f} word_delta={item_diff.word_delta:.2f}")
