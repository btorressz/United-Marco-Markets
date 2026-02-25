import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from backend.core.state_store import StateStore
from backend.compute.liquidation_heatmap import compute_heatmap

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/liquidation", tags=["liquidation"])

_store = StateStore()


@router.get("/heatmap")
def get_heatmap():
    try:
        price_snap = _store.get_snapshot("price:pyth:SOL_USD") or _store.get_snapshot("price:sol:pyth") or {}
        current_price = price_snap.get("price", 100.0)

        risk_snap = _store.get_snapshot("risk:status") or {}
        margin_usage = risk_snap.get("margin_usage", 0.3)

        regime = _store.get_snapshot("regime:latest") or {}
        vol_regime = regime.get("vol_regime", "normal")
        vol_map = {"low": 0.3, "normal": 0.5, "high": 0.8, "extreme": 1.2}
        vol = vol_map.get(vol_regime, 0.5)

        positions = []
        result = compute_heatmap(current_price, positions, vol, margin_usage)
        _store.set_snapshot("liquidation:heatmap", result, ttl=60)
        return result
    except Exception as exc:
        logger.error("Error computing liquidation heatmap: %s", exc, exc_info=True)
        return {
            "grid": [],
            "leverage_levels": [],
            "price_drops_pct": [],
            "ts": datetime.now(timezone.utc).isoformat(),
        }
