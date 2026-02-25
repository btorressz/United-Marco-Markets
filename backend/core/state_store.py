import os
import json
import logging
from datetime import datetime, timezone
from typing import Any

import redis

logger = logging.getLogger(__name__)

_THROTTLE_KEY = "risk:throttle"
_IDEMPOTENCY_PREFIX = "idem:"


class StateStore:

    def __init__(self, redis_url: str | None = None):
        self._redis_url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379")
        self._redis: redis.Redis | None = None

    def get_redis(self) -> redis.Redis | None:
        if self._redis is not None:
            try:
                self._redis.ping()
                return self._redis
            except Exception:
                self._redis = None

        try:
            self._redis = redis.Redis.from_url(self._redis_url, decode_responses=True)
            self._redis.ping()
            return self._redis
        except Exception:
            logger.warning("Redis unavailable at %s", self._redis_url)
            self._redis = None
            return None

    def set_snapshot(self, key: str, data: dict[str, Any], ttl: int | None = None) -> bool:
        r = self.get_redis()
        if r is None:
            return False
        try:
            serialized = json.dumps(data, default=str)
            if ttl:
                r.setex(key, ttl, serialized)
            else:
                r.set(key, serialized)
            return True
        except Exception:
            logger.warning("Failed to set snapshot for key=%s", key, exc_info=True)
            return False

    def get_snapshot(self, key: str) -> dict[str, Any] | None:
        r = self.get_redis()
        if r is None:
            return None
        try:
            raw = r.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            logger.warning("Failed to get snapshot for key=%s", key, exc_info=True)
            return None

    def set_risk_throttle(self, on: bool, reason: str = "", expiry_seconds: int = 300) -> bool:
        r = self.get_redis()
        if r is None:
            return False
        try:
            data = {
                "active": on,
                "reason": reason,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            serialized = json.dumps(data)
            if on:
                r.setex(_THROTTLE_KEY, expiry_seconds, serialized)
            else:
                r.delete(_THROTTLE_KEY)
            return True
        except Exception:
            logger.warning("Failed to set risk throttle", exc_info=True)
            return False

    def get_risk_throttle(self) -> dict[str, Any]:
        r = self.get_redis()
        if r is None:
            return {"active": False, "reason": "", "ts": ""}
        try:
            raw = r.get(_THROTTLE_KEY)
            if raw is None:
                return {"active": False, "reason": "", "ts": ""}
            data = json.loads(raw)
            return {
                "active": bool(data.get("active", False)),
                "reason": str(data.get("reason", "")),
                "ts": str(data.get("ts", "")),
            }
        except Exception:
            logger.warning("Failed to get risk throttle", exc_info=True)
            return {"active": False, "reason": "", "ts": ""}

    def set_idempotency_key(self, key: str, ttl: int = 60) -> bool:
        r = self.get_redis()
        if r is None:
            return False
        try:
            full_key = f"{_IDEMPOTENCY_PREFIX}{key}"
            result = r.set(full_key, "1", ex=ttl, nx=True)
            return bool(result)
        except Exception:
            logger.warning("Failed to set idempotency key=%s", key, exc_info=True)
            return False

    def check_idempotency_key(self, key: str) -> bool:
        r = self.get_redis()
        if r is None:
            return False
        try:
            full_key = f"{_IDEMPOTENCY_PREFIX}{key}"
            return r.exists(full_key) > 0
        except Exception:
            logger.warning("Failed to check idempotency key=%s", key, exc_info=True)
            return False
