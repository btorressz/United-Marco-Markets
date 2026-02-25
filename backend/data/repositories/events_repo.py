import json
import logging
from datetime import datetime, timezone

from backend.data.db import execute_query, execute_returning

logger = logging.getLogger(__name__)


class EventsRepository:

    def save_event(
        self,
        event_type: str,
        source: str,
        payload: dict | None = None,
    ) -> dict | None:
        try:
            return execute_returning(
                """INSERT INTO events (event_type, source, payload, ts)
                   VALUES (%s, %s, %s, %s) RETURNING id, event_type, source, payload, ts""",
                (event_type, source, json.dumps(payload or {}), datetime.now(timezone.utc)),
            )
        except Exception:
            logger.error("Failed to save event", exc_info=True)
            return None

    def get_recent(self, limit: int = 50) -> list[dict]:
        try:
            return execute_query(
                "SELECT id, event_type, source, payload, ts FROM events ORDER BY ts DESC LIMIT %s",
                (limit,),
            )
        except Exception:
            logger.error("Failed to get recent events", exc_info=True)
            return []

    def get_by_type(self, event_type: str, limit: int = 20) -> list[dict]:
        try:
            return execute_query(
                "SELECT id, event_type, source, payload, ts FROM events WHERE event_type = %s ORDER BY ts DESC LIMIT %s",
                (event_type, limit),
            )
        except Exception:
            logger.error("Failed to get events by type", exc_info=True)
            return []
