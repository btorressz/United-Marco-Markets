import math
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

LEVERAGE_LEVELS = [1, 2, 3, 5, 7, 10]
PRICE_DROPS_PCT = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]


def _liquidation_probability(leverage: int, drop_pct: float, vol: float, margin_usage: float) -> float:
    maintenance_margin = 1.0 / leverage
    loss_fraction = drop_pct / 100.0
    effective_loss = loss_fraction * leverage
    distance = maintenance_margin - (1.0 - effective_loss) if effective_loss >= (1.0 - maintenance_margin) else 0.0

    if effective_loss >= 1.0:
        return 1.0

    vol_annual = max(vol, 0.01)
    vol_daily = vol_annual / math.sqrt(365)

    z = (loss_fraction) / (vol_daily * math.sqrt(1))
    prob_from_vol = min(1.0, math.exp(-0.5 * z * z) if z > 0 else 1.0)

    margin_factor = 0.5 + 0.5 * min(margin_usage, 1.0)

    if effective_loss >= 1.0 - maintenance_margin:
        base_prob = min(1.0, effective_loss / (1.0 - maintenance_margin + 0.001))
    else:
        base_prob = effective_loss / max(1.0 - maintenance_margin, 0.01)

    combined = base_prob * margin_factor * (0.6 + 0.4 * prob_from_vol)
    return round(min(1.0, max(0.0, combined)), 4)


def compute_heatmap(current_price: float, positions: list, vol: float, margin_usage: float) -> dict:
    try:
        vol = max(vol, 0.0)
        margin_usage = max(0.0, min(margin_usage, 1.0))
        current_price = max(current_price, 0.01)

        grid = {}
        for lev in LEVERAGE_LEVELS:
            row = {}
            prev_prob = 0.0
            for drop in PRICE_DROPS_PCT:
                prob = _liquidation_probability(lev, drop, vol, margin_usage)
                prob = max(prob, prev_prob)
                row[str(drop)] = prob
                prev_prob = prob
            grid[str(lev)] = row

        for drop in PRICE_DROPS_PCT:
            prev_prob = 0.0
            for lev in LEVERAGE_LEVELS:
                current = grid[str(lev)][str(drop)]
                enforced = max(current, prev_prob)
                grid[str(lev)][str(drop)] = enforced
                prev_prob = enforced

        total_notional = 0.0
        for pos in (positions or []):
            size = abs(pos.get("size", 0))
            price = pos.get("entry_price", current_price)
            total_notional += size * price

        return {
            "current_price": current_price,
            "leverage_levels": LEVERAGE_LEVELS,
            "price_drops_pct": PRICE_DROPS_PCT,
            "grid": grid,
            "vol_used": round(vol, 4),
            "margin_usage": round(margin_usage, 4),
            "total_notional": round(total_notional, 2),
            "positions_count": len(positions or []),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.warning("Liquidation heatmap computation failed: %s", e)
        grid = {}
        for lev in LEVERAGE_LEVELS:
            row = {}
            for drop in PRICE_DROPS_PCT:
                row[str(drop)] = 0.0
            grid[str(lev)] = row
        return {
            "current_price": current_price if current_price else 0.0,
            "leverage_levels": LEVERAGE_LEVELS,
            "price_drops_pct": PRICE_DROPS_PCT,
            "grid": grid,
            "vol_used": 0.0,
            "margin_usage": 0.0,
            "total_notional": 0.0,
            "positions_count": 0,
            "ts": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
        }
