import numpy as np
import pandas as pd


class ShockCalculator:

    def compute_attention_score(self, articles_df: pd.DataFrame) -> float:
        if articles_df.empty:
            return 0.0
        volume = len(articles_df)
        score = np.log1p(volume)
        return float(score)

    def compute_tone_score(self, articles_df: pd.DataFrame) -> float:
        if articles_df.empty:
            return 0.0
        if "tone" not in articles_df.columns:
            return 0.0
        avg_tone = articles_df["tone"].mean()
        negativity = max(-avg_tone, 0.0)
        return float(negativity)

    def compute_shock_score(
        self,
        attention: float,
        tone: float,
        history_df: pd.DataFrame,
    ) -> float:
        raw = attention * (1.0 + tone)

        if history_df.empty or "shock_raw" not in history_df.columns:
            return float(raw)

        trailing = history_df["shock_raw"].dropna()
        if len(trailing) < 2:
            return float(raw)

        mean = trailing.mean()
        std = trailing.std(ddof=1)
        if std == 0:
            return 0.0

        z_score = (raw - mean) / std
        return float(z_score)

    def is_spike(self, shock_score: float, threshold: float = 2.0) -> bool:
        return shock_score > threshold
