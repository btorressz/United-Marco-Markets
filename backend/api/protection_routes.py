from __future__ import annotations

from typing import Any
from fastapi import APIRouter
from backend.core.state_store import StateStore
from backend.compute.geopolitical_risk import compute_geopolitical_index
from backend.compute.portfolio_protection import protection_protocol

router = APIRouter(prefix="/api/protection", tags=["protection"])
_store = StateStore()


def _geo():
    try:
        state = {"gdelt": _store.get_snapshot("gdelt:latest"), "wits": _store.get_snapshot("wits:tariff:USA:ALL:ALL") or _store.get_snapshot("wits:latest"), "stablecoin": _store.get_snapshot("stablecoin:health:latest")}
    except Exception:
        state = {"provider_error": True}
    return compute_geopolitical_index(state)


@router.get("/status")
def protection_status():
    return protection_protocol({"geopolitical_index": _geo(), "data_quality": _geo().get("data_quality", "degraded")})


@router.post("/preview")
def protection_preview(body: dict[str, Any] | None = None):
    body = body or {}
    return protection_protocol({**body, "geopolitical_index": body.get("geopolitical_index") or _geo()})
