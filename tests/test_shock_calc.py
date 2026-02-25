import pytest
import pandas as pd
import numpy as np
from backend.compute.shock_calc import ShockCalculator


class TestShockCalculator:

    @pytest.fixture
    def calculator(self):
        """Setup shock calculator."""
        return ShockCalculator()

    def test_attention_score(self, calculator):
        """Test volume-based attention scoring."""
        articles_df = pd.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "headline": ["tariff news"] * 5,
            "tone": [0.1, 0.2, -0.3, 0.0, -0.1],
        })

        score = calculator.compute_attention_score(articles_df)

        assert isinstance(score, float)
        assert score > 0.0
        assert score == np.log1p(5)

    def test_attention_score_single_article(self, calculator):
        """Test attention score with single article."""
        articles_df = pd.DataFrame({
            "id": [1],
            "headline": ["tariff news"],
            "tone": [0.1],
        })

        score = calculator.compute_attention_score(articles_df)

        assert isinstance(score, float)
        assert score > 0.0
        assert score == np.log1p(1)

    def test_attention_score_empty(self, calculator):
        """Test attention score with empty DataFrame."""
        articles_df = pd.DataFrame({
            "id": [],
            "headline": [],
            "tone": [],
        })

        score = calculator.compute_attention_score(articles_df)

        assert score == 0.0

    def test_tone_score(self, calculator):
        """Test sentiment tone scoring."""
        articles_df = pd.DataFrame({
            "tone": [-0.5, -0.3, -0.8],
        })

        score = calculator.compute_tone_score(articles_df)

        assert isinstance(score, float)
        assert score >= 0.0
        avg_tone = articles_df["tone"].mean()
        expected = max(-avg_tone, 0.0)
        assert abs(score - expected) < 1e-6

    def test_tone_score_positive_sentiment(self, calculator):
        """Test tone score with positive sentiment."""
        articles_df = pd.DataFrame({
            "tone": [0.5, 0.3, 0.8],
        })

        score = calculator.compute_tone_score(articles_df)

        assert score == 0.0

    def test_tone_score_mixed_sentiment(self, calculator):
        """Test tone score with mixed sentiment."""
        articles_df = pd.DataFrame({
            "tone": [-0.5, 0.2, -0.1],
        })

        score = calculator.compute_tone_score(articles_df)

        assert isinstance(score, float)
        assert score >= 0.0

    def test_tone_score_empty(self, calculator):
        """Test tone score with empty DataFrame."""
        articles_df = pd.DataFrame({
            "tone": [],
        })

        score = calculator.compute_tone_score(articles_df)

        assert score == 0.0

    def test_tone_score_missing_column(self, calculator):
        """Test tone score when tone column is missing."""
        articles_df = pd.DataFrame({
            "id": [1, 2],
            "headline": ["news1", "news2"],
        })

        score = calculator.compute_tone_score(articles_df)

        assert score == 0.0

    def test_shock_score_spike_detection(self, calculator):
        """Test z-score spike detection."""
        history_df = pd.DataFrame({
            "shock_raw": [1.0, 1.1, 0.9, 1.0, 1.05],
        })

        raw_score = 10.0
        shock_score = calculator.compute_shock_score(
            attention=5.0,
            tone=1.0,
            history_df=history_df,
        )

        assert isinstance(shock_score, float)
        assert shock_score > 2.0

    def test_shock_score_no_spike_normal_data(self, calculator):
        """Test that normal data does not trigger spike."""
        history_df = pd.DataFrame({
            "shock_raw": [10.0, 10.5, 9.8, 10.1, 9.9],
        })

        shock_score = calculator.compute_shock_score(
            attention=3.0,
            tone=0.5,
            history_df=history_df,
        )

        assert isinstance(shock_score, float)
        assert shock_score < 2.0

    def test_is_spike_true(self, calculator):
        """Test spike detection threshold."""
        assert calculator.is_spike(2.5) is True
        assert calculator.is_spike(3.0) is True
        assert calculator.is_spike(2.1) is True

    def test_is_spike_false(self, calculator):
        """Test non-spike values."""
        assert calculator.is_spike(2.0) is False
        assert calculator.is_spike(1.9) is False
        assert calculator.is_spike(0.0) is False
        assert calculator.is_spike(-1.0) is False

    def test_is_spike_custom_threshold(self, calculator):
        """Test spike detection with custom threshold."""
        assert calculator.is_spike(1.5, threshold=1.0) is True
        assert calculator.is_spike(0.9, threshold=1.0) is False
        assert calculator.is_spike(3.0, threshold=2.5) is True

    def test_shock_score_empty_history(self, calculator):
        """Test shock score with empty history."""
        empty_df = pd.DataFrame({
            "shock_raw": [],
        })

        shock_score = calculator.compute_shock_score(
            attention=3.0,
            tone=0.5,
            history_df=empty_df,
        )

        assert isinstance(shock_score, float)
        assert shock_score == 3.0 * (1.0 + 0.5)

    def test_shock_score_insufficient_history(self, calculator):
        """Test shock score with insufficient history for std dev."""
        history_df = pd.DataFrame({
            "shock_raw": [1.0],
        })

        shock_score = calculator.compute_shock_score(
            attention=3.0,
            tone=0.5,
            history_df=history_df,
        )

        assert isinstance(shock_score, float)
        assert shock_score == 3.0 * (1.0 + 0.5)

    def test_shock_score_zero_std(self, calculator):
        """Test shock score when standard deviation is zero."""
        history_df = pd.DataFrame({
            "shock_raw": [1.0, 1.0, 1.0, 1.0],
        })

        shock_score = calculator.compute_shock_score(
            attention=3.0,
            tone=0.5,
            history_df=history_df,
        )

        assert shock_score == 0.0
