from __future__ import annotations

from fastapi import APIRouter
from backend.compute.portfolio_explainability import explain_portfolio, explain_recommendation
from backend.compute.capital_allocator import allocate
from backend.core.state_store import StateStore

router = APIRouter(prefix="/api/explain", tags=["explain"])
_store = StateStore()


@router.get("/portfolio")
def portfolio_explanation():
    return explain_portfolio(allocate({}), (_store.get_snapshot("agents:signals") or {}).get("signals", []), _store.get_snapshot("data_quality:latest") or {})


@router.get("/recommendation/{rec_id}")
def recommendation_explanation(rec_id: str):
    return explain_recommendation(rec_id)
