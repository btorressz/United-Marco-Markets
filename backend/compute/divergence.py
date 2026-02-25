import pandas as pd


class DivergenceDetector:

    def compute_spread(self, series_a: pd.Series, series_b: pd.Series) -> pd.Series:
        aligned_a, aligned_b = series_a.align(series_b, join="inner")
        midpoint = (aligned_a + aligned_b) / 2.0
        midpoint = midpoint.replace(0, float("nan"))
        spread_pct = ((aligned_a - aligned_b) / midpoint) * 100.0
        return spread_pct

    def detect_divergence(
        self,
        spread: pd.Series,
        threshold_pct: float = 2.0,
        min_duration_minutes: int = 5,
    ) -> list[dict]:
        if spread.empty:
            return []

        alerts: list[dict] = []
        above = spread.abs() > threshold_pct
        in_divergence = False
        start_ts = None

        for ts, is_above in above.items():
            if is_above and not in_divergence:
                in_divergence = True
                start_ts = ts
            elif not is_above and in_divergence:
                in_divergence = False
                if start_ts is not None:
                    duration = (ts - start_ts).total_seconds() / 60.0
                    if duration >= min_duration_minutes:
                        window = spread.loc[start_ts:ts]
                        alerts.append({
                            "start": start_ts,
                            "end": ts,
                            "duration_minutes": round(duration, 2),
                            "max_spread_pct": round(float(window.abs().max()), 4),
                            "mean_spread_pct": round(float(window.mean()), 4),
                        })
                start_ts = None

        if in_divergence and start_ts is not None:
            last_ts = spread.index[-1]
            duration = (last_ts - start_ts).total_seconds() / 60.0
            if duration >= min_duration_minutes:
                window = spread.loc[start_ts:]
                alerts.append({
                    "start": start_ts,
                    "end": last_ts,
                    "duration_minutes": round(duration, 2),
                    "max_spread_pct": round(float(window.abs().max()), 4),
                    "mean_spread_pct": round(float(window.mean()), 4),
                    "ongoing": True,
                })

        return alerts

    def compute_basis(self, perp_price: float, spot_price: float) -> float:
        if spot_price == 0:
            return 0.0
        return ((perp_price - spot_price) / spot_price) * 100.0
