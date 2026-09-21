"""
tests/test_nlp_scorer.py -- Additional edge-case tests for NLPScorer
Day 10 Commit 1
"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from edgar.nlp_scorer import NLPScorer, _sentiment_score, _edit_ratio


class TestEdgeCases:
    @pytest.fixture
    def scorer(self):
        return NLPScorer()

    def test_empty_texts(self, scorer):
        result = scorer.score("", "")
        assert result.materiality == 0.0

    def test_very_long_text(self, scorer):
        long = "The company reported growth. " * 500
        result = scorer.score(long, long)
        assert result.structural_change == 0.0

    def test_unicode_handling(self, scorer):
        # Should not crash on unicode
        result = scorer.score("RÃ©sumÃ© and naÃ¯ve cafÃ©", "Ãber alles")
        assert 0.0 <= result.materiality <= 1.0

    def test_only_punctuation(self, scorer):
        result = scorer.score("!!!???...", "---===***")
        assert 0.0 <= result.materiality <= 1.0

    def test_repeated_material_keywords(self, scorer):
        old = "Operations normal."
        new = " ".join(["material weakness fraud restatement"] * 20)
        result = scorer.score(old, new)
        # Score should be capped at 1.0
        assert result.materiality <= 1.0
        assert result.keyword_score == 1.0  # should hit cap

    def test_sentiment_delta_on_polarity_flip(self, scorer):
        old = "Strong growth and excellent profitability."
        new = "Significant loss, weak performance, adverse conditions."
        result = scorer.score(old, new)
        # Flipping from positive to negative â large sentiment delta
        assert result.sentiment_delta > 0.1

    def test_high_edit_ratio_low_keywords(self, scorer):
        old = "alpha beta gamma delta epsilon"
        new = "zeta eta theta iota kappa"
        result = scorer.score(old, new)
        assert result.structural_change > 0.5
        assert result.keyword_score == 0.0

    def test_weight_sum_validation(self):
        with pytest.raises((AssertionError, ValueError)):
            NLPScorer(kw_weight=0.5, snt_weight=0.5, edit_weight=0.5)


class TestMaterialityThreshold:
    def test_default_threshold(self):
        from edgar.nlp_scorer import MaterialityResult
        r = MaterialityResult(
            materiality=0.40, keyword_score=0.5,
            sentiment_delta=0.2, structural_change=0.3,
        )
        assert r.is_material()

    def test_custom_threshold(self):
        from edgar.nlp_scorer import MaterialityResult
        r = MaterialityResult(
            materiality=0.20, keyword_score=0.1,
            sentiment_delta=0.1, structural_change=0.1,
        )
        assert r.is_material(threshold=0.1)
        assert not r.is_material(threshold=0.5)
