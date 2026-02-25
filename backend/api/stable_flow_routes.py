import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from backend.core.state_store import StateStore
from backend.compute.stable_flow import compute_flow_momentum, get_history
from backend.compute.stablecoin_health import StablecoinHealthMonitor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stable-flow", tags=["stable-flow"])

_store = StateStore()


@router.get("/latest")
def get_latest():
    try:
        stable_prices = {}
        stable_volumes = {}
        for symbol in StablecoinHealthMonitor.STABLES:
            snap = _store.get_snapshot(f"price:{symbol.lower()}:pyth")
            if not snap:
                snap = _store.get_snapshot(f"price:{symbol.lower()}:kraken")
            if snap and snap.get("price"):
                stable_prices[symbol] = snap["price"]
            vol_snap = _store.get_snapshot(f"volume:{symbol.lower()}")
            if vol_snap and vol_snap.get("volume"):
                stable_volumes[symbol] = vol_snap["volume"]

        total_mc = 0
        mc_snap = _store.get_snapshot("market:total_cap")
        if mc_snap:
            total_mc = mc_snap.get("total_market_cap", 0)

        result = compute_flow_momentum(stable_prices, stable_volumes, total_mc)
        _store.set_snapshot("stable_flow:latest", result, ttl=60)
        return result
    except Exception as exc:
        logger.error("Error computing stable flow: %s", exc, exc_info=True)
        return {
            "stable_flow_momentum": 0,
            "risk_on_off_indicator": "neutral",
            "drivers": [],
            "ts": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/history")
def get_flow_history():
    try:
        return {"history": get_history(50), "ts": datetime.now(timezone.utc).isoformat()}
    except Exception:
        return {"history": [], "ts": datetime.now(timezone.utc).isoformat()}
