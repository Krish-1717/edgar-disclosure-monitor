"""
tests/test_diff_sections.py -- Tests for EDGAR section diffing
Day 9 Commit 2
"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from edgar.nlp_scorer import (
    NLPScorer, MaterialityResult,
    _tokenize, _sentiment_score, _keyword_density, _edit_ratio,
)


class TestTokenizer:
    def test_basic(self):
        assert _tokenize("Hello, World!") == ["hello", "world"]

    def test_empty(self):
        assert _tokenize("") == []

    def test_contraction(self):
        tokens = _tokenize("we're growing")
        assert "we're" in tokens or "we" in tokens


class TestSentiment:
    def test_positive_text(self):
        score = _sentiment_score("Revenue growth exceeded expectations with strong profitability.")
        assert score > 0

    def test_negative_text(self):
        score = _sentiment_score("Revenue declined significantly with weak margins and loss.")
        assert score < 0

    def test_negation(self):
        pos = _sentiment_score("strong growth")
        neg = _sentiment_score("not strong growth")
        assert pos > neg

    def test_neutral_range(self):
        score = _sentiment_score("The company filed its annual report.")
        assert -0.5 < score < 0.5


class TestKeywordDensity:
    def test_high_materiality_keywords(self):
        text = "The company disclosed material weakness in internal controls and going concern."
        score, found = _keyword_density(text)
        assert score > 0
        assert "material weakness" in found or "going concern" in found

    def test_no_keywords(self):
        score, found = _keyword_density("The weather is nice today.")
        assert score == 0.0
        assert found == []

    def test_score_capped_at_one(self):
        text = " ".join(["fraud restatement bankruptcy default"] * 10)
        score, _ = _keyword_density(text)
        assert score <= 1.0


class TestEditRatio:
    def test_identical_text_zero(self):
        t = "the quick brown fox jumps over the lazy dog"
        assert _edit_ratio(t, t) == 0.0

    def test_completely_different(self):
        r = _edit_ratio("cat dog bird", "fish whale shark")
        assert r == 1.0

    def test_partial_change(self):
        r = _edit_ratio("revenue growth was strong", "revenue decline was significant")
        assert 0.0 < r < 1.0

    def test_both_empty(self):
        assert _edit_ratio("", "") == 0.0


class TestNLPScorer:
    @pytest.fixture
    def scorer(self):
        return NLPScorer()

    def test_material_filing_change(self, scorer):
        old = "Revenue grew 10% year-over-year. Operations remained stable."
        new = (
            "The company identified a material weakness in internal controls. "
            "Management has initiated a restatement of prior financial statements. "
            "An SEC investigation is ongoing."
        )
        result = scorer.score(old, new)
        assert result.materiality > 0.3
        assert result.is_material()
        assert len(result.keywords_found) > 0

    def test_immaterial_change(self, scorer):
        old = "The company operates in the technology sector."
        new = "The company operates in the technology and software sector."
        result = scorer.score(old, new)
        assert result.materiality < 0.5

    def test_result_bounds(self, scorer):
        result = scorer.score("Some old text here.", "Some new text there.")
        assert 0.0 <= result.materiality <= 1.0
        assert 0.0 <= result.keyword_score <= 1.0
        assert 0.0 <= result.sentiment_delta <= 1.0
        assert 0.0 <= result.structural_change <= 1.0

    def test_score_sections(self, scorer):
        sections = {
            "risk_factors": ("Low risk environment.", "High fraud and litigation risk."),
            "mda": ("Good growth.", "Good growth continued."),
        }
        results = scorer.score_sections(sections)
        assert set(results.keys()) == {"risk_factors", "mda"}
        assert results["risk_factors"].materiality > results["mda"].materiality

    def test_summary_string(self, scorer):
        result = scorer.score("old text", "new text with fraud and restatement issues")
        s = result.summary()
        assert "materiality=" in s
        assert "MATERIAL" in s or "not material" in s

    def test_custom_weights(self):
        scorer = NLPScorer(kw_weight=0.8, snt_weight=0.1, edit_weight=0.1)
        text = "Material weakness and restatement and fraud discovered."
        result = scorer.score("normal operations", text)
        assert result.keyword_score > 0
