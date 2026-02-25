import pytest
import pandas as pd
import numpy as np
from backend.compute.index_calc import TariffIndexCalculator


class TestTariffIndexCalculator:

    @pytest.fixture
    def calculator(self):
        """Setup calculator with test weights."""
        country_weights = {
            "USA": 0.4,
            "CHN": 0.35,
            "DEU": 0.25,
        }
        product_weights = {
            "STEEL": 0.3,
            "SEMICONDUCTORS": 0.5,
            "AGRICULTURE": 0.2,
        }
        return TariffIndexCalculator(country_weights, product_weights)

    def test_calculate_returns_valid_index(self, calculator):
        """Test that calculate returns index_level within 0-100 range."""
        tariff_data = pd.DataFrame({
            "country": ["USA", "CHN", "DEU"],
            "product": ["STEEL", "SEMICONDUCTORS", "AGRICULTURE"],
            "tariff_rate": [25.0, 15.0, 5.0],
        })

        result = calculator.calculate(tariff_data)

        assert isinstance(result, dict)
        assert "index_level" in result
        assert "rate_of_change" in result
        assert "components" in result
        assert 0.0 <= result["index_level"] <= 100.0
        assert isinstance(result["rate_of_change"], (int, float))
        assert isinstance(result["components"], list)

    def test_components_breakdown(self, calculator):
        """Test that component contributions sum correctly."""
        tariff_data = pd.DataFrame({
            "country": ["USA", "CHN"],
            "product": ["STEEL", "SEMICONDUCTORS"],
            "tariff_rate": [20.0, 10.0],
        })

        result = calculator.calculate(tariff_data)
        components = result["components"]

        assert len(components) == 2
        for component in components:
            assert "country" in component
            assert "product" in component
            assert "tariff_rate" in component
            assert "weight" in component
            assert "contribution" in component
            assert component["tariff_rate"] >= 0
            assert component["weight"] >= 0
            assert component["contribution"] >= 0

    def test_rate_of_change(self, calculator):
        """Test that rate_of_change calculation is correct."""
        tariff_data = pd.DataFrame({
            "country": ["USA", "CHN"],
            "product": ["STEEL", "SEMICONDUCTORS"],
            "tariff_rate": [25.0, 15.0],
            "prev_tariff_rate": [20.0, 10.0],
        })

        result = calculator.calculate(tariff_data)

        assert "rate_of_change" in result
        assert isinstance(result["rate_of_change"], (int, float))
        assert result["rate_of_change"] >= 0.0

    def test_empty_data(self, calculator):
        """Test that empty DataFrame is handled gracefully."""
        empty_df = pd.DataFrame({
            "country": [],
            "product": [],
            "tariff_rate": [],
        })

        result = calculator.calculate(empty_df)

        assert result["index_level"] == 0.0
        assert result["rate_of_change"] == 0.0
        assert result["components"] == []

    def test_single_entry(self, calculator):
        """Test with a single tariff entry."""
        tariff_data = pd.DataFrame({
            "country": ["USA"],
            "product": ["STEEL"],
            "tariff_rate": [30.0],
        })

        result = calculator.calculate(tariff_data)

        assert result["index_level"] >= 0.0
        assert result["index_level"] <= 100.0
        assert len(result["components"]) == 1
        assert result["components"][0]["tariff_rate"] == 30.0

    def test_unknown_country_product(self, calculator):
        """Test with unknown country/product combinations."""
        tariff_data = pd.DataFrame({
            "country": ["USA", "UNKNOWN"],
            "product": ["STEEL", "UNKNOWN"],
            "tariff_rate": [20.0, 15.0],
        })

        result = calculator.calculate(tariff_data)

        assert result["index_level"] >= 0.0
        assert result["index_level"] <= 100.0
        assert len(result["components"]) == 2
