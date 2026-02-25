import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from backend.core.event_bus import EventBus
from backend.compute.replay_engine import run_replay, get_latest_replay

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/replay", tags=["replay"])

_bus = EventBus()


@router.post("/run")
def run_replay_endpoint(body: dict = {}):
    try:
        events = _bus.get_recent(limit=body.get("limit", 200))
        result = run_replay(
            events=events,
            strategy_config=body.get("strategy_config"),
            start_ts=body.get("start_ts"),
            end_ts=body.get("end_ts"),
        )
        return result
    except Exception as exc:
        logger.error("Replay run failed: %s", exc, exc_info=True)
        return {"status": "error", "error": str(exc), "ts": datetime.now(timezone.utc).isoformat()}


@router.get("/latest")
def get_latest():
    result = get_latest_replay()
    if result:
        return result
    return {"status": "no_replay", "message": "No replay run yet", "ts": datetime.now(timezone.utc).isoformat()}
