from __future__ import annotations

from fastapi import APIRouter
from backend.core.state_store import StateStore
from backend.compute.signal_attribution import compute_signal_outcomes, attribution_summary

router = APIRouter(prefix="/api/signals", tags=["signals"])
_store = StateStore()


def _signals():
    return (_store.get_snapshot("agents:signals") or {}).get("signals", [])


@router.get("/outcomes")
def outcomes():
    return compute_signal_outcomes(_signals())


@router.get("/attribution")
def attribution():
    return attribution_summary(_signals())
