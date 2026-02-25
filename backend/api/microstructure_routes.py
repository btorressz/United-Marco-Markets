import logging
from datetime import datetime, timezone
from fastapi import APIRouter

from backend.core.state_store import StateStore
from backend.compute.microstructure import MicrostructureAnalyzer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/microstructure", tags=["microstructure"])

_analyzer = MicrostructureAnalyzer()
_store = StateStore()


@router.get("/imbalance")
def get_imbalance():
    cached = _store.get_snapshot("microstructure:latest")
    if cached:
        return cached
    return {
        "imbalance": 0.0,
        "bias": "neutral",
        "liquidity_thin": False,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/dislocations")
def get_dislocations():
    prices = {}
    for venue in ["pyth", "kraken", "coingecko", "hyperliquid", "drift"]:
        snap = _store.get_snapshot(f"price:sol:{venue}")
        if snap and snap.get("price"):
            prices[venue] = snap["price"]

    if len(prices) < 2:
        return {"alerts": [], "ts": datetime.now(timezone.utc).isoformat()}

    alerts = _analyzer.detect_dislocation(prices)
    return {"alerts": alerts, "ts": datetime.now(timezone.utc).isoformat()}


@router.get("/basis")
def get_basis():
    perp_snap = _store.get_snapshot("price:sol:hyperliquid")
    spot_snap = _store.get_snapshot("price:sol:kraken")

    if not perp_snap or not spot_snap:
        return {"basis": None, "ts": datetime.now(timezone.utc).isoformat()}

    opp = _analyzer.detect_basis_opportunity(
        perp_snap.get("price", 0),
        spot_snap.get("price", 0),
    )
    return {"basis": opp, "ts": datetime.now(timezone.utc).isoformat()}
