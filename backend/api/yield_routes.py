import logging
from datetime import datetime, timezone
from fastapi import APIRouter

from backend.core.state_store import StateStore
from backend.compute.stable_yield import StableYieldCalculator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/yield", tags=["yield"])

_calc = StableYieldCalculator()
_store = StateStore()


@router.get("/carry")
def get_carry_scores():
    funding_rates = {}

    hl_fund = _store.get_snapshot("funding:hyperliquid:latest")
    if hl_fund and "funding_rate" in hl_fund:
        funding_rates["hyperliquid"] = hl_fund["funding_rate"]

    drift_fund = _store.get_snapshot("funding:drift:latest")
    if drift_fund and "funding_rate" in drift_fund:
        funding_rates["drift"] = drift_fund["funding_rate"]

    if not funding_rates:
        funding_rates = {"hyperliquid": 0.0001, "drift": 0.00008}

    scores = _calc.compute_carry_scores(funding_rates)
    return {
        "carry_scores": scores,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/summary")
def get_yield_summary():
    carry = _store.get_snapshot("carry:latest")
    if carry:
        return carry
    return {
        "message": "No carry data cached yet",
        "ts": datetime.now(timezone.utc).isoformat(),
    }
