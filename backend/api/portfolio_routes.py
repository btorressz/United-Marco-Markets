import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from backend.core.state_store import StateStore
from backend.compute.portfolio_optimizer import optimize as portfolio_optimize

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

_store = StateStore()


@router.get("/proposal")
def get_proposal(method: str = Query("risk_parity")):
    try:
        idx = _store.get_snapshot("index:latest") or {}
        regime = _store.get_snapshot("regime:latest") or {}
        carry_snap = _store.get_snapshot("carry:latest") or {}
        predict = _store.get_snapshot("prediction:latest") or {}

        vol_regime = regime.get("vol_regime", "normal")
        macro_regime = "risk_off" if idx.get("shock_score", 0) > 1.5 else "normal"
        if vol_regime in ("high", "extreme"):
            macro_regime = "risk_off"

        inputs = {
            "risk_limit": 0.5,
            "predictor_prob": predict.get("probability", 0.5),
            "carry_score": carry_snap.get("carry_score", 0),
            "macro_regime": macro_regime,
            "stable_rotation_pref": 0.0,
            "method": method,
        }

        result = portfolio_optimize(inputs)
        _store.set_snapshot("portfolio:proposal", result, ttl=60)
        return result
    except Exception as exc:
        logger.error("Error computing portfolio proposal: %s", exc, exc_info=True)
        return {
            "allocation": {"hl_perps": 0.25, "drift_perps": 0.25, "spot_jupiter": 0.25, "stablecoins": 0.25},
            "method": method,
            "reasoning": ["Error computing proposal, using equal weights"],
            "ts": datetime.now(timezone.utc).isoformat(),
        }
