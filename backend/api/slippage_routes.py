import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from backend.core.state_store import StateStore
from backend.compute.slippage_model import compute_max_safe_sizes, get_multi_venue_slippage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/slippage", tags=["slippage"])

_store = StateStore()


def _get_venue_params() -> dict:
    venues = {}

    micro = _store.get_snapshot("microstructure:latest") or {}
    eqi_snap = _store.get_snapshot("eqi:latest") or {}

    venues["hyperliquid"] = {
        "ob_depth": micro.get("liquidity_depth", 0),
        "spread_bps": micro.get("spread_bps", 5.0),
        "volatility": 0.03,
        "recent_slippage_bps": eqi_snap.get("avg_slippage_bps", 0),
    }

    solana_snap = _store.get_snapshot("solana:quality") or {}
    venues["jupiter"] = {
        "ob_depth": 0,
        "spread_bps": solana_snap.get("components", {}).get("spread_score", 5.0),
        "volatility": 0.03,
        "recent_slippage_bps": 0,
    }

    venues["drift"] = {
        "ob_depth": 0,
        "spread_bps": 8.0,
        "volatility": 0.03,
        "recent_slippage_bps": 0,
    }

    return venues


@router.get("/latest")
def get_latest():
    try:
        venue_data = _get_venue_params()
        result = get_multi_venue_slippage(venue_data)
        return result
    except Exception as exc:
        logger.error("Slippage model error: %s", exc, exc_info=True)
        return {"venues": {}, "ts": datetime.now(timezone.utc).isoformat()}


@router.post("/estimate")
def estimate_slippage(body: dict = {}):
    try:
        venue = body.get("venue", "hyperliquid")
        venue_params = _get_venue_params()
        params = venue_params.get(venue, {"ob_depth": 0, "spread_bps": 5.0, "volatility": 0.03, "recent_slippage_bps": 0})
        result = compute_max_safe_sizes(
            ob_depth=params.get("ob_depth", 0),
            spread_bps=params.get("spread_bps", 5.0),
            volatility=params.get("volatility", 0.03),
            recent_slippage_bps=params.get("recent_slippage_bps", 0),
            venue=venue,
        )
        return result
    except Exception as exc:
        logger.error("Slippage estimate error: %s", exc, exc_info=True)
        return {"venue": body.get("venue", "unknown"), "error": "estimation_failed", "ts": datetime.now(timezone.utc).isoformat()}
