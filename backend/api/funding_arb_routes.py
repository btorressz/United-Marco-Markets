import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from backend.core.state_store import StateStore
from backend.compute.funding_arb import detect_arb, get_history

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/funding-arb", tags=["funding-arb"])

_store = StateStore()


@router.get("/latest")
def get_latest():
    try:
        hl_snap = _store.get_snapshot("funding:hyperliquid") or {}
        drift_snap = _store.get_snapshot("funding:drift") or {}

        hl_funding = hl_snap.get("funding_rate", 0.0)
        drift_funding = drift_snap.get("funding_rate", 0.0)
        now = datetime.now(timezone.utc).isoformat()
        hl_ts = hl_snap.get("ts", now)
        drift_ts = drift_snap.get("ts", now)

        result = detect_arb(hl_funding, drift_funding, hl_ts, drift_ts)
        _store.set_snapshot("funding_arb:latest", result, ttl=60)
        return result
    except Exception as exc:
        logger.error("Error detecting funding arb: %s", exc, exc_info=True)
        return {
            "arb_signal": "none",
            "spread_bps": 0,
            "persistence_minutes": 0,
            "expected_net_carry": 0,
            "ts": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/history")
def get_arb_history():
    try:
        return {"history": get_history(), "ts": datetime.now(timezone.utc).isoformat()}
    except Exception:
        return {"history": [], "ts": datetime.now(timezone.utc).isoformat()}
