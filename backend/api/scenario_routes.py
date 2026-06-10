from __future__ import annotations

from fastapi import APIRouter
from backend.compute.scenario_engine import scenario_templates, run_scenario

router = APIRouter(prefix="/api/scenario", tags=["scenario"])


@router.get("/templates")
def templates():
    return scenario_templates()


@router.post("/run")
def run(body: dict | None = None):
    return run_scenario(body or {})
