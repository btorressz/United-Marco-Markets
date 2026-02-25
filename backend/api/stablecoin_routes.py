import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Query

from backend.core.state_store import StateStore
from backend.compute.stablecoin_health import StablecoinHealthMonitor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stablecoins", tags=["stablecoins"])

_monitor = StablecoinHealthMonitor()
_store = StateStore()


def _get_stable_prices() -> dict[str, float]:
    prices = {}
    for symbol in StablecoinHealthMonitor.STABLES:
        snap = _store.get_snapshot(f"price:{symbol.lower()}:pyth")
        if snap and snap.get("price"):
            prices[symbol] = snap["price"]
        else:
            snap = _store.get_snapshot(f"price:{symbol.lower()}:kraken")
            if snap and snap.get("price"):
                prices[symbol] = snap["price"]
            else:
                prices[symbol] = 1.0
    return prices


@router.get("/latest")
def get_latest():
    prices = _get_stable_prices()
    health = _monitor.compute_health(prices)
    _store.set_snapshot("stablecoin:health", health, ttl=60)
    return health


@router.get("/history")
def get_history(window: str = Query("7d")):
    cached = _store.get_snapshot("stablecoin:history")
    if cached:
        return cached
    return {"window": window, "points": []}


@router.get("/health")
def get_health():
    cached = _store.get_snapshot("stablecoin:health")
    if cached:
        alerts = _monitor.get_alerts(cached)
        stress_data = {}
        for symbol, data in cached.items():
            if isinstance(data, dict):
                stress = _monitor.detect_stress(
                    data.get("depeg_bps", 0), 0.0, 0.0
                )
                peg_prob = _monitor.compute_peg_break_probability(data.get("depeg_bps", 0))
                stress_data[symbol] = {
                    **data,
                    "stress": stress,
                    "peg_break_probability": peg_prob,
                }
        return {"health": stress_data, "alerts": alerts, "ts": datetime.now(timezone.utc).isoformat()}

    prices = _get_stable_prices()
    health = _monitor.compute_health(prices)
    return {"health": health, "alerts": [], "ts": datetime.now(timezone.utc).isoformat()}


@router.get("/alerts")
def get_alerts():
    cached = _store.get_snapshot("stablecoin:health")
    if cached:
        return {"alerts": _monitor.get_alerts(cached)}
    return {"alerts": []}
