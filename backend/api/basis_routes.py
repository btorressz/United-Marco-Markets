import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from backend.core.state_store import StateStore
from backend.compute.basis_engine import compute_basis, assess_feasibility, get_history as get_basis_history_data

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/basis", tags=["basis"])

_store = StateStore()


@router.get("/latest")
def get_latest():
    try:
        hl_snap = _store.get_snapshot("price:hyperliquid:SOL_PERP") or {}
        drift_snap = _store.get_snapshot("price:drift:SOL_PERP") or {}
        spot_snap = _store.get_snapshot("price:pyth:SOL_USD") or _store.get_snapshot("price:sol:pyth") or _store.get_snapshot("price:sol:kraken") or {}

        hl_perp = hl_snap.get("price", 0)
        drift_perp = drift_snap.get("price", 0)
        spot = spot_snap.get("price", 0)

        hl_funding_snap = _store.get_snapshot("funding:hyperliquid") or {}
        drift_funding_snap = _store.get_snapshot("funding:drift") or {}
        hl_funding = hl_funding_snap.get("funding_rate", 0)
        drift_funding = drift_funding_snap.get("funding_rate", 0)

        result = compute_basis(hl_perp, drift_perp, spot, hl_funding, drift_funding)
        _store.set_snapshot("basis:latest", result, ttl=30)
        return result
    except Exception as exc:
        logger.error("Error computing basis: %s", exc, exc_info=True)
        return {
            "annualized_basis_bps": 0,
            "net_carry": 0,
            "execution_feasibility_score": 0,
            "ts": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/feasibility")
def get_feasibility():
    try:
        micro = _store.get_snapshot("microstructure:latest") or {}
        integrity = _store.get_snapshot("price:integrity") or {}

        spread_bps = micro.get("spread_bps", 0)
        liquidity_depth = micro.get("liquidity_depth", 100000)
        integrity_status = integrity.get("status", "OK")

        score = assess_feasibility(spread_bps, liquidity_depth, integrity_status)
        return {
            "feasibility_score": score,
            "spread_bps": spread_bps,
            "liquidity_depth": liquidity_depth,
            "integrity_status": integrity_status,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.error("Error assessing feasibility: %s", exc, exc_info=True)
        return {"feasibility_score": 0, "ts": datetime.now(timezone.utc).isoformat()}


@router.get("/history")
def get_basis_history():
    try:
        history = get_basis_history_data(50)
        return {"history": history, "ts": datetime.now(timezone.utc).isoformat()}
    except Exception:
        return {"history": [], "ts": datetime.now(timezone.utc).isoformat()}
