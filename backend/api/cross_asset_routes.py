from __future__ import annotations

from fastapi import APIRouter
from backend.compute.cross_asset_intelligence import compute_correlations, demo_series, detect_contagion

router = APIRouter(prefix="/api/cross-asset", tags=["cross-asset"])


@router.get("/correlations")
def correlations():
    return compute_correlations(demo_series())


@router.get("/contagion")
def contagion():
    return detect_contagion()
