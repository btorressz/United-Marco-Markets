import logging

from fastapi import APIRouter, HTTPException, Query

from backend.core.schemas import EventResponse
from backend.data.repositories.events_repo import EventsRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])

_events_repo = EventsRepository()


@router.get("/", response_model=list[EventResponse])
def get_recent_events(limit: int = Query(default=50, ge=1, le=500)):
    try:
        rows = _events_repo.get_recent(limit=limit)
        results = []
        for r in rows:
            payload = r.get("payload", {})
            if isinstance(payload, str):
                import json
                payload = json.loads(payload)
            results.append(EventResponse(
                id=str(r["id"]),
                event_type=r["event_type"],
                source=r["source"],
                payload=payload,
                ts=r["ts"],
            ))
        return results
    except Exception as exc:
        logger.error("Error fetching recent events: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch recent events")


@router.get("/by-type", response_model=list[EventResponse])
def get_events_by_type(type: str = Query(...), limit: int = Query(default=20, ge=1, le=200)):
    try:
        rows = _events_repo.get_by_type(event_type=type, limit=limit)
        results = []
        for r in rows:
            payload = r.get("payload", {})
            if isinstance(payload, str):
                import json
                payload = json.loads(payload)
            results.append(EventResponse(
                id=str(r["id"]),
                event_type=r["event_type"],
                source=r["source"],
                payload=payload,
                ts=r["ts"],
            ))
        return results
    except Exception as exc:
        logger.error("Error fetching events by type: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch events by type")
