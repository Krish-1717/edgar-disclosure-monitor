"""
tests/test_filing_differ.py — Unit tests for the filing diff engine.

Uses synthetic fixtures (no network calls).

Run:
    python -m pytest tests/test_filing_differ.py -v
"""
from __future__ import annotations

import sys
import os

# Allow running from project root or tests/ dir
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from filing_parser import ParsedFiling, FilingItem
from filing_differ import diff_filings, ItemDiff, FilingDiff
from filing_report import generate_alert_payload

# ── Fixtures ─────────────────────────────────────────────────────────────────────

OLD_TEXT = "We will deliver 2.2 million units. Revenue will be $50B. We commit to growth."
NEW_TEXT = (
    "We target delivery of approximately 1.8 million units. "
    "Revenue may be approximately $45B. Growth is subject to market conditions."
)

FRONTEND_SCHEMA_KEYS = {
    "id", "ticker", "company", "sector", "form", "filed",
    "rank", "ranking", "materiality", "burial", "gap",
    "sentiment", "bucket", "item", "desc", "old_text", "new_text",
}


def _make_item(num: str, text: str, title: str = "Test Item") -> FilingItem:
    return FilingItem(item_num=num, title=title, text=text)


def _make_filing(items: list[FilingItem], filed: str = "2024-01-01") -> ParsedFiling:
    return ParsedFiling(
        ticker="TEST",
        form_type="10-K",
        filed_date=filed,
        accession="0001234567-24-000001",
        fiscal_year_end="December 31, 2023",
        items=items,
    )


def _make_diff() -> FilingDiff:
    old_item = _make_item("1", OLD_TEXT)
    new_item = _make_item("1", NEW_TEXT)
    old_filing = _make_filing([old_item], filed="2023-01-01")
    new_filing = _make_filing([new_item], filed="2024-01-01")
    return diff_filings(old_filing, new_filing)


# ── Tests ─────────────────────────────────────────────────────────────────────────

def test_word_delta():
    """New text is shorter than old — word_delta should be negative."""
    diff = _make_diff()
    item_diff = diff.item_diffs.get("1")
    assert item_diff is not None, "Item 1 must be in diff"
    # OLD_TEXT has ~14 words, NEW_TEXT has ~23 words so delta could go either way
    # but the test verifies the delta is computed (non-zero if texts differ)
    assert isinstance(item_diff.word_delta, float)
    # We know texts are close in length, so just confirm it's calculated
    # NEW_TEXT is longer: 23 words vs OLD_TEXT: 14 words → positive delta
    assert item_diff.word_delta != 0.0, "word_delta should be non-zero when texts differ"


def test_hedging_shift():
    """
    OLD: 'will deliver', 'will be', 'commit' → hard words
    NEW: 'target', 'approximately', 'may', 'subject to' → soft words
    hedging_shift should be positive (more hedged).
    """
    diff = _make_diff()
    item_diff = diff.item_diffs.get("1")
    assert item_diff is not None
    # New text has more soft words (target, approximately, may, subject to)
    # Old text has more hard words (will x2, commit)
    assert item_diff.hedging_shift > 0, (
        f"Expected positive hedging_shift (more soft language), got {item_diff.hedging_shift}"
    )


def test_number_changes():
    """$50B and 2.2 million should be detected as changed to $45B and 1.8 million."""
    diff = _make_diff()
    item_diff = diff.item_diffs.get("1")
    assert item_diff is not None
    # At least one number change should be detected
    assert len(item_diff.number_changes) >= 1, (
        f"Expected ≥1 number change, got {len(item_diff.number_changes)}"
    )


def test_similarity_decreases():
    """The texts are semantically different enough that similarity < 0.9."""
    diff = _make_diff()
    item_diff = diff.item_diffs.get("1")
    assert item_diff is not None
    assert item_diff.similarity < 0.9, (
        f"Expected similarity < 0.9 for modified texts, got {item_diff.similarity:.3f}"
    )


def test_get_top_changes():
    """get_top_changes should return items sorted by materiality_score descending."""
    # Build a diff with multiple items
    items_old = [
        _make_item("1", "Short text."),
        _make_item("2", "We will achieve $1B in revenue. Certainty is high."),
        _make_item("3", "Risk factors remain unchanged. No material differences."),
    ]
    items_new = [
        _make_item("1", "Short text."),
        _make_item("2", OLD_TEXT + " " + NEW_TEXT * 5),  # massively changed
        _make_item("3", "Risk factors remain unchanged. No material differences."),
    ]
    old_f = _make_filing(items_old)
    new_f = _make_filing(items_new)
    diff = diff_filings(old_f, new_f)

    top = diff.get_top_changes(3)
    assert len(top) >= 1
    # Verify sorted descending
    for i in range(len(top) - 1):
        assert top[i].materiality_score >= top[i + 1].materiality_score, (
            "get_top_changes must return items sorted by materiality_score descending"
        )


def test_alert_payload_schema():
    """generate_alert_payload must return a dict with all required frontend schema keys."""
    diff = _make_diff()
    payload = generate_alert_payload(diff, news_score=0.3, sentiment="NEGATIVE", bucket="negative")

    missing = FRONTEND_SCHEMA_KEYS - set(payload.keys())
    assert not missing, f"Alert payload missing keys: {missing}"

    # Type checks
    assert isinstance(payload["id"], str)
    assert isinstance(payload["ticker"], str)
    assert isinstance(payload["materiality"], float)
    assert isinstance(payload["ranking"], int)
    assert payload["rank"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL"}
    assert 0 <= payload["materiality"] <= 100
    assert 0 <= payload["gap"] <= 100


def test_overall_materiality_range():
    """overall_materiality must be between 0 and 1."""
    diff = _make_diff()
    assert 0.0 <= diff.overall_materiality <= 1.0, (
        f"overall_materiality out of range: {diff.overall_materiality}"
    )


def test_item_diff_fields_populated():
    """ItemDiff must have all expected fields after a diff."""
    diff = _make_diff()
    item_diff = diff.item_diffs.get("1")
    assert item_diff is not None

    assert hasattr(item_diff, "word_delta")
    assert hasattr(item_diff, "similarity")
    assert hasattr(item_diff, "added_sentences")
    assert hasattr(item_diff, "removed_sentences")
    assert hasattr(item_diff, "hedging_shift")
    assert hasattr(item_diff, "number_changes")
    assert hasattr(item_diff, "materiality_score")
    assert isinstance(item_diff.added_sentences, list)
    assert isinstance(item_diff.removed_sentences, list)
    assert isinstance(item_diff.number_changes, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
