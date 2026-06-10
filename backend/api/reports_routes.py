from __future__ import annotations

from fastapi import APIRouter
from backend.compute.report_generator import build_report

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/daily-brief")
def daily_brief():
    return build_report("daily_brief")


@router.get("/tariff-risk")
def tariff_risk():
    return build_report("tariff_risk")


@router.get("/portfolio-risk")
def portfolio_risk():
    return build_report("portfolio_risk")


@router.get("/agent-signals")
def agent_signals():
    return build_report("agent_signals")
