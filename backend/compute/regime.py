import numpy as np
import pandas as pd


class RegimeDetector:

    def detect_funding_regime(self, funding_series: pd.Series) -> str:
        if funding_series.empty:
            return "neutral"

        avg_rate = funding_series.mean()

        if avg_rate > 0.0001:
            return "contango"
        elif avg_rate < -0.0001:
            return "backwardation"
        return "neutral"

    def detect_regime_flip(self, current: str, previous: str) -> bool:
        return current != previous

    def detect_vol_regime(self, returns_series: pd.Series) -> str:
        if returns_series.empty or len(returns_series) < 2:
            return "normal"

        vol = returns_series.std(ddof=1) * np.sqrt(252)

        if vol < 0.15:
            return "low"
        elif vol < 0.50:
            return "normal"
        elif vol < 1.00:
            return "high"
        return "extreme"
