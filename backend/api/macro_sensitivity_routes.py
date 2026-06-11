from __future__ import annotations

from fastapi import APIRouter
from backend.api.equities_routes import _overview_rows
from backend.core.state_store import StateStore
from backend.compute.macro_sensitivity import score_assets, score_asset_sensitivity

router = APIRouter(prefix="/api/macro-sensitivity", tags=["macro-sensitivity"])
_store = StateStore()


def _inputs():
    idx = _store.get_snapshot("index:latest") or {}
    gdelt = _store.get_snapshot("gdelt:latest") or {}
    return float(idx.get("rate_of_change", idx.get("change", 0.0)) or 0.0), float(gdelt.get("shock_score", gdelt.get("tone_shock", 0.0)) or 0.0), not bool(idx) or not bool(gdelt)


@router.get("/assets")
def macro_sensitivity_assets():
    tariff, gdelt, degraded = _inputs()
    return score_assets(_overview_rows(), tariff, gdelt, degraded)


@router.get("/{ticker}")
def macro_sensitivity_ticker(ticker: str):
    tariff, gdelt, degraded = _inputs()
    row = next((r for r in _overview_rows() if r.get("ticker") == ticker.upper()), {"ticker": ticker.upper(), "sector": "Unknown", "degraded": True})
    return score_asset_sensitivity(row, tariff, gdelt, degraded or row.get("degraded", False))
