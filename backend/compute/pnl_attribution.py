import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class PnLAttributor:

    def attribute(
        self,
        total_pnl: float,
        position_size: float,
        entry_price: float,
        current_price: float,
        funding_accumulated: float = 0.0,
        tariff_index_delta: float = 0.0,
        shock_score: float = 0.0,
        realized_vol: float = 0.0,
        slippage_cost: float = 0.0,
        basis_pnl: float = 0.0,
    ) -> dict:
        price_pnl = position_size * (current_price - entry_price)
        macro_proxy = -abs(tariff_index_delta * 0.01 * position_size * current_price)
        if shock_score > 1.0:
            macro_proxy *= (1 + shock_score * 0.1)

        vol_drift = 0.0
        if realized_vol > 0.5:
            vol_drift = -abs(total_pnl) * 0.05 * realized_vol

        unexplained = total_pnl - (price_pnl + funding_accumulated + macro_proxy + basis_pnl - slippage_cost + vol_drift)

        return {
            "total_pnl": round(total_pnl, 2),
            "price_pnl": round(price_pnl, 2),
            "funding_income": round(funding_accumulated, 2),
            "macro_effect": round(macro_proxy, 2),
            "basis_spread": round(basis_pnl, 2),
            "execution_slippage": round(-slippage_cost, 2),
            "volatility_drift": round(vol_drift, 2),
            "unexplained": round(unexplained, 2),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
