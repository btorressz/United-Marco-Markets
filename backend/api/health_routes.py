import time
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from backend.core.schemas import HealthResponse
from backend.core.state_store import StateStore
from backend.data.db import check_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])

_state_store = StateStore()
_start_time = time.time()

_FEED_DEFINITIONS: list[dict[str, Any]] = [
    {"name": "Pyth", "key": "price:pyth:SOL_USD", "is_authoritative": True, "interval_seconds": 30},
    {"name": "Kraken", "key": "price:kraken:SOL_USD", "is_authoritative": False, "interval_seconds": 30},
    {"name": "CoinGecko", "key": "price:coingecko:SOL_USD", "is_authoritative": False, "interval_seconds": 60},
    {"name": "Hyperliquid", "key": "price:hyperliquid:SOL/USD", "is_authoritative": False, "interval_seconds": 60},
    {"name": "Drift", "key": "price:drift:SOL_PERP", "is_authoritative": False, "interval_seconds": 60},
    {"name": "WITS", "key": "wits:tariff:USA:ALL:ALL", "is_authoritative": True, "interval_seconds": 21600},
    {"name": "GDELT", "key": "gdelt:latest", "is_authoritative": False, "interval_seconds": 300},
]

_WARNING_MULTIPLIER = 3
_ERROR_MULTIPLIER = 10


def _get_feed_status(feed_def: dict[str, Any], now: datetime) -> dict[str, Any]:
    name = feed_def["name"]
    key = feed_def["key"]
    is_auth = feed_def["is_authoritative"]
    interval = feed_def["interval_seconds"]

    result: dict[str, Any] = {
        "name": name,
        "last_update_ts": None,
        "age_seconds": None,
        "status": "error",
        "is_authoritative": is_auth,
    }

    try:
        snapshot = _state_store.get_snapshot(key)
        if snapshot is None:
            result["status"] = "error"
            return result

        ts_raw = snapshot.get("ts")
        if ts_raw:
            if isinstance(ts_raw, str):
                try:
                    ts = datetime.fromisoformat(ts_raw)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                except ValueError:
                    ts = None
            elif isinstance(ts_raw, (int, float)):
                ts = datetime.fromtimestamp(ts_raw, tz=timezone.utc)
            else:
                ts = None
        else:
            ts = None

        if ts is None:
            result["status"] = "fallback"
            return result

        age = (now - ts).total_seconds()
        result["last_update_ts"] = ts.isoformat()
        result["age_seconds"] = round(age, 1)

        if age <= interval * _WARNING_MULTIPLIER:
            result["status"] = "ok"
        elif age <= interval * _ERROR_MULTIPLIER:
            result["status"] = "warning"
        else:
            result["status"] = "error"

    except Exception:
        logger.warning("Error checking feed status for %s", name, exc_info=True)
        result["status"] = "fallback"

    return result


@router.get("/", response_model=HealthResponse)
def health_check():
    try:
        db_ok = check_connection()
    except Exception:
        db_ok = False

    try:
        r = _state_store.get_redis()
        redis_ok = r is not None
    except Exception:
        redis_ok = False

    uptime = time.time() - _start_time

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        version="0.1.0",
        database=db_ok,
        redis=redis_ok,
        uptime_seconds=round(uptime, 2),
        ts=datetime.now(timezone.utc),
    )


@router.get("/feeds")
def feed_status():
    now = datetime.now(timezone.utc)
    feeds = [_get_feed_status(fd, now) for fd in _FEED_DEFINITIONS]
    ok_count = sum(1 for f in feeds if f["status"] == "ok")
    total = len(feeds)
    overall = "ok" if ok_count == total else "degraded" if ok_count > 0 else "error"
    return {
        "status": overall,
        "feeds": feeds,
        "ok_count": ok_count,
        "total": total,
        "ts": now.isoformat(),
    }
