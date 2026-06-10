import uuid
import logging
import math
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_executions: dict[str, dict] = {}


def create_smart_execution(
    venue: str,
    market: str,
    side: str,
    total_size: float,
    n_slices: int,
    interval_seconds: int,
    execution_style: str,
    max_slippage_bps: float = 50.0,
    strategy_id: str | None = None,
) -> dict[str, Any]:
    exec_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    n_slices = max(1, min(n_slices, 50))
    interval_seconds = max(5, min(interval_seconds, 3600))
    slice_size = round(total_size / n_slices, 8)
    last_slice_size = round(total_size - slice_size * (n_slices - 1), 8)

    plan = {
        "exec_id": exec_id,
        "venue": venue,
        "market": market,
        "side": side,
        "total_size": total_size,
        "executed_size": 0.0,
        "n_slices": n_slices,
        "completed_slices": 0,
        "slice_size": slice_size,
        "last_slice_size": last_slice_size,
        "interval_seconds": interval_seconds,
        "execution_style": execution_style,
        "max_slippage_bps": max_slippage_bps,
        "strategy_id": strategy_id,
        "status": "active",
        "slices": [],
        "estimated_slippage_bps": 0.0,
        "actual_slippage_bps": 0.0,
        "created_at": now.isoformat(),
        "next_slice_at": now.isoformat(),
        "completed_at": None,
    }

    _executions[exec_id] = plan
    logger.info("Smart execution created: %s %s %s total=%.4f slices=%d style=%s",
                exec_id[:8], side, market, total_size, n_slices, execution_style)
    return plan


def get_execution(exec_id: str) -> dict[str, Any] | None:
    return _executions.get(exec_id)


def get_active_executions() -> list[dict[str, Any]]:
    return [e for e in _executions.values() if e["status"] == "active"]


def get_all_executions(limit: int = 20) -> list[dict[str, Any]]:
    all_e = sorted(_executions.values(), key=lambda e: e["created_at"], reverse=True)
    return all_e[:limit]


def record_slice_fill(
    exec_id: str,
    fill_price: float,
    fill_size: float,
    slippage_bps: float = 0.0,
) -> dict[str, Any] | None:
    plan = _executions.get(exec_id)
    if not plan or plan["status"] != "active":
        return None

    now = datetime.now(timezone.utc)
    plan["completed_slices"] += 1
    plan["executed_size"] = round(plan["executed_size"] + fill_size, 8)

    slice_record = {
        "slice_num": plan["completed_slices"],
        "fill_price": fill_price,
        "fill_size": fill_size,
        "slippage_bps": slippage_bps,
        "ts": now.isoformat(),
    }
    plan["slices"].append(slice_record)

    filled_slippages = [s["slippage_bps"] for s in plan["slices"]]
    if filled_slippages:
        plan["actual_slippage_bps"] = round(sum(filled_slippages) / len(filled_slippages), 2)

    if plan["completed_slices"] >= plan["n_slices"]:
        plan["status"] = "completed"
        plan["completed_at"] = now.isoformat()
        logger.info("Smart execution completed: %s total_size=%.4f", exec_id[:8], plan["executed_size"])
    else:
        from datetime import timedelta
        next_at = now + timedelta(seconds=plan["interval_seconds"])
        plan["next_slice_at"] = next_at.isoformat()

    return plan


def abort_execution(exec_id: str, reason: str = "user_cancelled") -> dict[str, Any] | None:
    plan = _executions.get(exec_id)
    if not plan:
        return None
    plan["status"] = "aborted"
    plan["abort_reason"] = reason
    plan["completed_at"] = datetime.now(timezone.utc).isoformat()
    logger.info("Smart execution aborted: %s reason=%s", exec_id[:8], reason)
    return plan


def get_next_slice_size(exec_id: str) -> float:
    plan = _executions.get(exec_id)
    if not plan or plan["status"] != "active":
        return 0.0
    remaining = plan["n_slices"] - plan["completed_slices"]
    if remaining <= 1:
        return max(0.0, plan["total_size"] - plan["executed_size"])
    return plan["slice_size"]


def compute_vwap_price(prices: list[float], volumes: list[float]) -> float:
    if not prices or not volumes or len(prices) != len(volumes):
        return sum(prices) / len(prices) if prices else 0.0
    total_vol = sum(volumes)
    if total_vol <= 0:
        return sum(prices) / len(prices)
    return sum(p * v for p, v in zip(prices, volumes)) / total_vol


def estimate_twap_slippage(total_size: float, n_slices: int, market_slippage_bps: float = 5.0) -> float:
    if n_slices <= 0:
        return market_slippage_bps
    slice_size = total_size / n_slices
    urgency_discount = max(0.3, 1.0 - (n_slices - 1) * 0.05)
    return round(market_slippage_bps * urgency_discount, 2)
