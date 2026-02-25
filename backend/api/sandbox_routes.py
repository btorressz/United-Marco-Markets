import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from backend.core.state_store import StateStore
from backend.compute.strategy_sandbox import run_sandbox, get_latest, get_history

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])

_store = StateStore()


def _build_market_state() -> dict:
    state = {}
    price_snap = _store.get_snapshot("price:pyth:SOL_USD") or _store.get_snapshot("price:sol:pyth") or {}
    state["current_price"] = price_snap.get("price", 100.0)

    idx = _store.get_snapshot("index:latest") or {}
    state["tariff_index"] = idx.get("tariff_index", 0)
    state["shock_score"] = idx.get("shock_score", 0)

    regime = _store.get_snapshot("regime:latest") or {}
    state["vol_regime"] = regime.get("vol_regime", "normal")
    state["funding_regime"] = regime.get("funding_regime", "neutral")

    micro = _store.get_snapshot("microstructure:latest") or {}
    state["spread_bps"] = micro.get("spread_bps", 5.0)

    state["price_change_pct"] = 0.0
    state["volatility"] = 0.03
    return state


@router.post("/run")
def run_comparison(body: dict = {}):
    try:
        market_state = _build_market_state()
        market_state.update(body.get("market_state", {}))
        result = run_sandbox(
            config_a=body.get("config_a"),
            config_b=body.get("config_b"),
            market_state=market_state,
        )
        return result
    except Exception as exc:
        logger.error("Sandbox run failed: %s", exc, exc_info=True)
        return {"error": "Sandbox run failed", "ts": datetime.now(timezone.utc).isoformat()}


@router.get("/latest")
def get_latest_result():
    result = get_latest()
    if result:
        return result
    return {"message": "No sandbox comparison run yet", "ts": datetime.now(timezone.utc).isoformat()}


@router.get("/history")
def get_sandbox_history():
    return {"history": get_history(), "ts": datetime.now(timezone.utc).isoformat()}
