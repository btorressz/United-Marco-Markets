import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from backend.core.state_store import StateStore
from backend.compute.solana_liquidity import compute_quality, assess_congestion, estimate_jupiter_route

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/solana", tags=["solana"])

_store = StateStore()


@router.get("/quality")
def get_quality():
    try:
        micro = _store.get_snapshot("microstructure:latest") or {}
        spread_bps = micro.get("spread_bps", 10)
        ob_depth = micro.get("liquidity_depth", 100000)

        rpc_snap = _store.get_snapshot("solana:rpc_latency")
        rpc_latency_ms = rpc_snap.get("latency_ms", 50) if rpc_snap else 50

        route_snap = _store.get_snapshot("jupiter:route")
        price_impact_bps = route_snap.get("price_impact_bps", 5) if route_snap else 5

        quality = compute_quality(spread_bps, price_impact_bps, rpc_latency_ms, ob_depth)
        _store.set_snapshot("solana:quality", quality, ttl=30)
        return quality
    except Exception as exc:
        logger.error("Error computing Solana quality: %s", exc, exc_info=True)
        return {
            "execution_quality_score": 0,
            "congestion_warning": False,
            "slippage_risk": "unknown",
            "ts": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/congestion")
def get_congestion():
    try:
        rpc_snap = _store.get_snapshot("solana:rpc_latency")
        rpc_latency_ms = rpc_snap.get("latency_ms", 50) if rpc_snap else 50
        slot_delta = rpc_snap.get("slot_delta", 1) if rpc_snap else 1

        return assess_congestion(rpc_latency_ms, slot_delta)
    except Exception as exc:
        logger.error("Error assessing congestion: %s", exc, exc_info=True)
        return {
            "congested": False,
            "severity": "low",
            "reasons": [],
            "recommended_action": "proceed",
            "ts": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/jupiter-route")
def get_jupiter_route():
    try:
        route = estimate_jupiter_route()
        return route
    except Exception as exc:
        logger.error("Error estimating Jupiter route: %s", exc, exc_info=True)
        return {
            "estimated_hops": 0,
            "price_impact_bps": 0,
            "estimated_slippage_bps": 0,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
