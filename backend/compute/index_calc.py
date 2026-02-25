import numpy as np
import pandas as pd


class TariffIndexCalculator:

    def __init__(self, country_weights: dict[str, float], product_weights: dict[str, float]):
        self.country_weights = country_weights
        self.product_weights = product_weights

    def calculate(self, tariff_data: pd.DataFrame) -> dict:
        if tariff_data.empty:
            return {
                "index_level": 0.0,
                "rate_of_change": 0.0,
                "components": [],
            }

        components = []
        weighted_sum = 0.0
        total_weight = 0.0

        for _, row in tariff_data.iterrows():
            country = row.get("country", "")
            product = row.get("product", "")
            rate = float(row.get("tariff_rate", 0.0))

            cw = self.country_weights.get(country, 0.0)
            pw = self.product_weights.get(product, 0.0)
            combined_weight = cw * pw if cw and pw else max(cw, pw)

            contribution = rate * combined_weight
            weighted_sum += contribution
            total_weight += combined_weight

            components.append({
                "country": country,
                "product": product,
                "tariff_rate": rate,
                "weight": combined_weight,
                "contribution": contribution,
            })

        raw_index = weighted_sum / total_weight if total_weight > 0 else 0.0
        index_level = self._normalize(raw_index)

        rate_of_change = 0.0
        if "prev_tariff_rate" in tariff_data.columns:
            prev_weighted = 0.0
            prev_total = 0.0
            for _, row in tariff_data.iterrows():
                country = row.get("country", "")
                product = row.get("product", "")
                prev_rate = float(row.get("prev_tariff_rate", 0.0))
                cw = self.country_weights.get(country, 0.0)
                pw = self.product_weights.get(product, 0.0)
                combined_weight = cw * pw if cw and pw else max(cw, pw)
                prev_weighted += prev_rate * combined_weight
                prev_total += combined_weight
            prev_index = self._normalize(prev_weighted / prev_total if prev_total > 0 else 0.0)
            if prev_index > 0:
                rate_of_change = ((index_level - prev_index) / prev_index) * 100.0
            else:
                rate_of_change = 100.0 if index_level > 0 else 0.0

        return {
            "index_level": round(index_level, 4),
            "rate_of_change": round(rate_of_change, 4),
            "components": components,
        }

    def _normalize(self, value: float, max_rate: float = 100.0) -> float:
        clamped = np.clip(value, 0.0, max_rate)
        return float((clamped / max_rate) * 100.0)
