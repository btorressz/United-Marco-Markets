import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from backend.compute.backtester import run_backtest
from backend.core.state_store import StateStore
from backend.core.event_bus import EventBus, EventType

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/backtest", tags=["backtest"])

_store = StateStore()
_bus = EventBus()

_LATEST_KEY = "desk:backtest:latest"
_LATEST_TTL = 1800
_HISTORY: list[dict[str, Any]] = []
_MAX_HISTORY = 20


@router.post("/run")
def run_backtest_endpoint(body: dict[str, Any] | None = None):
    config = body or {}

    _bus.emit(
        EventType.BACKTEST_STARTED,
        source="backtest_routes",
        payload={
            "strategy": config.get("strategy", "momentum"),
            "window_days": config.get("window_days", 30),
            "venue": config.get("venue", "hyperliquid"),
        },
    )

    try:
        result = run_backtest(config)
    except Exception as exc:
        logger.warning("Backtest failed: %s", exc, exc_info=True)
        return {
            "success": False,
            "error": str(exc),
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    result["success"] = True
    _store.set_snapshot(_LATEST_KEY, result, ttl=_LATEST_TTL)

    summary = {
        "total_return_pct": result.get("total_return_pct"),
        "sharpe_ratio": result.get("sharpe_ratio"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "trade_count": result.get("trade_count"),
        "config": result.get("config", {}),
        "ts": result.get("ts"),
    }
    _HISTORY.append(summary)
    if len(_HISTORY) > _MAX_HISTORY:
        _HISTORY.pop(0)

    _bus.emit(
        EventType.BACKTEST_COMPLETED,
        source="backtest_routes",
        payload={
            "total_return_pct": result.get("total_return_pct"),
            "sharpe_ratio": result.get("sharpe_ratio"),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "trade_count": result.get("trade_count"),
        },
    )

    return result


@router.get("/latest")
def get_latest_backtest():
    cached = _store.get_snapshot(_LATEST_KEY)
    if cached:
        return cached
    return {
        "available": False,
        "message": "No backtest results yet. POST to /api/backtest/run to start one.",
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/history")
def get_backtest_history():
    return {
        "history": list(_HISTORY),
        "count": len(_HISTORY),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
