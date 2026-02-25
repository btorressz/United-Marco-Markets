import pytest
import pandas as pd
from datetime import datetime, timedelta
from backend.compute.divergence import DivergenceDetector


class TestDivergenceDetector:

    @pytest.fixture
    def detector(self):
        """Setup divergence detector."""
        return DivergenceDetector()

    def test_compute_spread(self, detector):
        """Test spread calculation between two price series."""
        timestamps = pd.date_range(start="2025-01-01", periods=5, freq="h")
        series_a = pd.Series([100.0, 101.0, 102.0, 101.5, 100.5], index=timestamps)
        series_b = pd.Series([98.0, 99.5, 100.5, 99.5, 98.5], index=timestamps)

        spread = detector.compute_spread(series_a, series_b)

        assert isinstance(spread, pd.Series)
        assert len(spread) == 5
        assert all(isinstance(x, (int, float)) for x in spread)

        midpoint = (100.0 + 98.0) / 2.0
        expected_first = ((100.0 - 98.0) / midpoint) * 100.0
        assert abs(spread.iloc[0] - expected_first) < 1e-5

    def test_compute_spread_identical_series(self, detector):
        """Test spread when series are identical."""
        timestamps = pd.date_range(start="2025-01-01", periods=3, freq="h")
        series_a = pd.Series([100.0, 100.0, 100.0], index=timestamps)
        series_b = pd.Series([100.0, 100.0, 100.0], index=timestamps)

        spread = detector.compute_spread(series_a, series_b)

        assert len(spread) == 3
        assert all(spread == 0.0)

    def test_compute_spread_misaligned_indices(self, detector):
        """Test spread with partially overlapping indices."""
        index_a = pd.date_range(start="2025-01-01", periods=5, freq="h")
        index_b = pd.date_range(start="2025-01-01 02:00", periods=5, freq="h")

        series_a = pd.Series([100.0, 101.0, 102.0, 101.5, 100.5], index=index_a)
        series_b = pd.Series([98.0, 99.5, 100.5, 99.5, 98.5], index=index_b)

        spread = detector.compute_spread(series_a, series_b)

        assert len(spread) == 3

    def test_detect_divergence(self, detector):
        """Test divergence detection when threshold is exceeded."""
        timestamps = pd.date_range(start="2025-01-01", periods=30, freq="1min")

        spread_values = [
            0.5, 0.6, 0.7, 0.8, 0.9, 1.0,
            2.5, 3.0, 3.5, 2.8, 3.1, 3.2, 3.0, 2.9, 2.8,
            0.4, 0.3, 0.2, 0.1, 0.0, 0.0,
            2.5, 3.1, 3.2, 3.0, 3.1, 0.4, 0.3, 0.2, 0.1,
        ]
        spread = pd.Series(spread_values, index=timestamps)

        alerts = detector.detect_divergence(spread, threshold_pct=2.0, min_duration_minutes=5)

        assert isinstance(alerts, list)
        assert len(alerts) > 0
        for alert in alerts:
            assert "start" in alert
            assert "end" in alert
            assert "duration_minutes" in alert
            assert "max_spread_pct" in alert
            assert "mean_spread_pct" in alert
            assert alert["duration_minutes"] >= 5.0

    def test_no_alert_below_threshold(self, detector):
        """Test no alert when spread stays below threshold."""
        timestamps = pd.date_range(start="2025-01-01", periods=20, freq="1min")
        spread = pd.Series([0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 0.9, 0.8, 0.7, 0.6], index=timestamps)

        alerts = detector.detect_divergence(spread, threshold_pct=2.0, min_duration_minutes=5)

        assert len(alerts) == 0

    def test_detect_divergence_short_duration_ignored(self, detector):
        """Test that short divergences below min duration are ignored."""
        timestamps = pd.date_range(start="2025-01-01", periods=10, freq="1min")

        spread_values = [0.5, 0.6, 3.0, 3.5, 0.4, 0.3, 0.2, 0.1, 0.0, 0.0]
        spread = pd.Series(spread_values, index=timestamps)

        alerts = detector.detect_divergence(spread, threshold_pct=2.0, min_duration_minutes=5)

        assert len(alerts) == 0

    def test_detect_divergence_ongoing(self, detector):
        """Test divergence detection with ongoing alert."""
        timestamps = pd.date_range(start="2025-01-01", periods=15, freq="1min")

        spread_values = [
            0.5, 0.6, 0.7, 2.5, 3.0, 3.5, 3.1, 3.2,
            3.3, 3.4, 3.1, 3.2, 3.0, 3.1, 3.2,
        ]
        spread = pd.Series(spread_values, index=timestamps)

        alerts = detector.detect_divergence(spread, threshold_pct=2.0, min_duration_minutes=5)

        assert len(alerts) > 0
        last_alert = alerts[-1]
        assert last_alert.get("ongoing") is True

    def test_detect_divergence_empty_series(self, detector):
        """Test divergence detection with empty series."""
        spread = pd.Series([], dtype=float)

        alerts = detector.detect_divergence(spread)

        assert alerts == []

    def test_detect_divergence_multiple_windows(self, detector):
        """Test detection of multiple separate divergence windows."""
        timestamps = pd.date_range(start="2025-01-01", periods=59, freq="1min")

        spread_values = [
            0.5, 0.6, 0.7, 0.8, 0.9, 1.0,
            2.5, 3.0, 3.1, 3.0, 3.2, 3.1, 3.0,
            0.4, 0.3, 0.2, 0.1, 0.0, 0.0, 0.1, 0.2,
            2.8, 3.0, 3.2, 3.1, 3.0, 3.1, 3.0, 3.2,
            0.2, 0.1, 0.0, 0.0, 0.0, 0.0, 0.1, 0.2,
            0.3, 0.4, 0.5, 0.6, 0.5, 0.4, 0.3, 0.2,
            0.1, 0.0, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0, 0.1,
        ]
        spread = pd.Series(spread_values, index=timestamps)

        alerts = detector.detect_divergence(spread, threshold_pct=2.0, min_duration_minutes=5)

        assert isinstance(alerts, list)
        assert all(isinstance(alert, dict) for alert in alerts)

    def test_compute_basis(self, detector):
        """Test basis calculation between perp and spot."""
        perp_price = 50.5
        spot_price = 50.0

        basis = detector.compute_basis(perp_price, spot_price)

        assert isinstance(basis, float)
        expected = ((50.5 - 50.0) / 50.0) * 100.0
        assert abs(basis - expected) < 1e-6

    def test_compute_basis_negative(self, detector):
        """Test negative basis."""
        perp_price = 49.5
        spot_price = 50.0

        basis = detector.compute_basis(perp_price, spot_price)

        expected = ((49.5 - 50.0) / 50.0) * 100.0
        assert abs(basis - expected) < 1e-6
        assert basis < 0.0

    def test_compute_basis_zero_spot(self, detector):
        """Test basis with zero spot price."""
        basis = detector.compute_basis(50.0, 0.0)

        assert basis == 0.0

    def test_compute_basis_large_spread(self, detector):
        """Test basis with large price divergence."""
        perp_price = 100.0
        spot_price = 50.0

        basis = detector.compute_basis(perp_price, spot_price)

        expected = ((100.0 - 50.0) / 50.0) * 100.0
        assert abs(basis - expected) < 1e-6
        assert abs(basis - 100.0) < 1e-6

    def test_detect_divergence_custom_threshold(self, detector):
        """Test divergence detection with custom threshold."""
        timestamps = pd.date_range(start="2025-01-01", periods=30, freq="1min")

        spread_values = [
            0.5, 0.6, 0.7, 0.8, 0.9,
            1.5, 1.8, 1.6, 1.7, 1.5, 1.6, 1.7,
            0.4, 0.3, 0.2, 0.1, 0.0, 0.0, 0.1, 0.2,
            1.5, 1.6, 1.7, 1.5, 1.6, 0.5, 0.4, 0.3, 0.2, 0.1,
        ]
        spread = pd.Series(spread_values, index=timestamps)

        alerts = detector.detect_divergence(spread, threshold_pct=1.0, min_duration_minutes=5)

        assert len(alerts) > 0
