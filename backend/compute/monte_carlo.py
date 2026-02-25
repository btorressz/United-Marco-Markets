import math
import logging
from datetime import datetime, timezone

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_N_PATHS = 2000
MAX_N_PATHS = 10000


class MonteCarloEngine:

    def run(
        self,
        current_price: float,
        position_size: float,
        volatility: float,
        horizon_hours: float = 4,
        n_paths: int = DEFAULT_N_PATHS,
        drift: float = 0.0,
        funding_rate: float = 0.0,
        shock_adjustment: float = 0.0,
        margin: float = 0.0,
        liq_price: float | None = None,
    ) -> dict:
        n_paths = min(max(n_paths, 100), MAX_N_PATHS)
        vol_adj = volatility * (1.0 + shock_adjustment)
        dt = horizon_hours / (365.25 * 24.0)
        sqrt_dt = math.sqrt(dt)

        rng = np.random.default_rng()
        z = rng.standard_normal(n_paths)

        log_returns = (drift - 0.5 * vol_adj ** 2) * dt + vol_adj * sqrt_dt * z
        end_prices = current_price * np.exp(log_returns)

        funding_cost = abs(position_size) * current_price * funding_rate * (horizon_hours / 8.0)
        pnl = position_size * (end_prices - current_price) - funding_cost

        pnl_sorted = np.sort(pnl)

        var_95 = float(-np.percentile(pnl, 5))
        var_99 = float(-np.percentile(pnl, 1))
        cvar_95 = float(-np.mean(pnl_sorted[:max(int(0.05 * n_paths), 1)]))
        cvar_99 = float(-np.mean(pnl_sorted[:max(int(0.01 * n_paths), 1)]))

        prob_loss_5pct = float(np.mean(pnl < -abs(position_size * current_price) * 0.05))
        prob_loss_10pct = float(np.mean(pnl < -abs(position_size * current_price) * 0.10))

        prob_liq = 0.0
        if liq_price is not None and position_size != 0:
            if position_size > 0:
                prob_liq = float(np.mean(end_prices <= liq_price))
            else:
                prob_liq = float(np.mean(end_prices >= liq_price))

        hist_bins = 50
        counts, edges = np.histogram(pnl, bins=hist_bins)

        return {
            "current_price": current_price,
            "position_size": position_size,
            "volatility": volatility,
            "horizon_hours": horizon_hours,
            "n_paths": n_paths,
            "var_95": round(var_95, 2),
            "var_99": round(var_99, 2),
            "cvar_95": round(cvar_95, 2),
            "cvar_99": round(cvar_99, 2),
            "expected_pnl": round(float(np.mean(pnl)), 2),
            "median_pnl": round(float(np.median(pnl)), 2),
            "std_pnl": round(float(np.std(pnl)), 2),
            "prob_loss_5pct": round(prob_loss_5pct, 4),
            "prob_loss_10pct": round(prob_loss_10pct, 4),
            "prob_liquidation": round(prob_liq, 4),
            "histogram": {
                "counts": counts.tolist(),
                "edges": [round(e, 2) for e in edges.tolist()],
            },
            "ts": datetime.now(timezone.utc).isoformat(),
        }
