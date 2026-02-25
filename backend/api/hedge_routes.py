import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from backend.core.state_store import StateStore
from backend.compute.hedge_ratio import compute_full_hedge_analysis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/hedge", tags=["hedge"])

_store = StateStore()


def _get_return_series() -> dict:
    returns = {}

    for asset in ["SOL", "BTC", "ETH"]:
        snap = _store.get_snapshot(f"returns:{asset.lower()}")
        if snap and isinstance(snap.get("returns"), list):
            returns[asset] = snap["returns"]

    if not returns:
        returns = {"SOL": [], "BTC": [], "ETH": []}

    return returns


@router.get("/latest")
def get_hedge_latest():
    try:
        returns = _get_return_series()

        idx_snap = _store.get_snapshot("index:latest") or {}
        shock_series_snap = _store.get_snapshot("shock:history")
        macro_shock_series = None
        if shock_series_snap and isinstance(shock_series_snap.get("values"), list):
            macro_shock_series = shock_series_snap["values"]

        result = compute_full_hedge_analysis(
            returns=returns,
            macro_shock_series=macro_shock_series,
            window=30,
        )
        return result
    except Exception as exc:
        logger.error("Hedge analysis error: %s", exc, exc_info=True)
        return {
            "correlations": {},
            "hedge_ratios": {},
            "macro_correlations": {},
            "best_hedge": None,
            "best_hedge_effectiveness": 0,
            "window": 30,
            "assets": [],
            "ts": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/correlations")
def get_correlations():
    try:
        returns = _get_return_series()
        from backend.compute.hedge_ratio import compute_rolling_correlations
        result = compute_rolling_correlations(returns, window=30)
        return result
    except Exception as exc:
        logger.error("Correlation error: %s", exc, exc_info=True)
        return {"correlations": {}, "assets": [], "window": 30, "ts": datetime.now(timezone.utc).isoformat()}
