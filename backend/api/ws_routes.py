import os
import json
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

_connected_clients: set[WebSocket] = set()


async def _get_state_snapshot() -> dict:
    from backend.core.state_store import StateStore
    store = StateStore()
    snapshot = {
        "type": "snapshot",
        "ts": datetime.now(timezone.utc).isoformat(),
        "message": "Connected to Tariff Risk Desk live feed",
    }
    try:
        throttle = store.get_risk_throttle()
        if throttle:
            snapshot["risk_throttle"] = throttle
        idx = store.get_snapshot("index:latest")
        if idx:
            snapshot["index"] = idx
    except Exception:
        pass
    return snapshot


async def _redis_listener(ws: WebSocket):
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    while True:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(redis_url, decode_responses=True)
            pubsub = r.pubsub()
            await pubsub.subscribe("desk:events")
            logger.info("WebSocket subscribed to desk:events")

            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = message["data"]
                        if isinstance(data, str):
                            event = json.loads(data)
                        else:
                            event = {"data": str(data)}
                        await ws.send_json(event)
                    except WebSocketDisconnect:
                        return
                    except Exception:
                        logger.debug("Failed to forward event to WS client")
                        return
        except WebSocketDisconnect:
            return
        except asyncio.CancelledError:
            return
        except Exception:
            logger.debug("Redis pubsub unavailable, retrying in 5s")
            await asyncio.sleep(5)


async def _heartbeat(ws: WebSocket):
    while True:
        try:
            await asyncio.sleep(15)
            await ws.send_json({"type": "heartbeat", "ts": datetime.now(timezone.utc).isoformat()})
        except Exception:
            return


@router.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    await ws.accept()
    _connected_clients.add(ws)
    logger.info("WebSocket client connected, total=%d", len(_connected_clients))

    listener_task = None
    heartbeat_task = None
    try:
        snapshot = await _get_state_snapshot()
        await ws.send_json(snapshot)

        listener_task = asyncio.create_task(_redis_listener(ws))
        heartbeat_task = asyncio.create_task(_heartbeat(ws))

        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_json({"type": "pong", "ts": datetime.now(timezone.utc).isoformat()})
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.debug("WebSocket error", exc_info=True)
    finally:
        if listener_task:
            listener_task.cancel()
        if heartbeat_task:
            heartbeat_task.cancel()
        _connected_clients.discard(ws)
        logger.info("WebSocket client disconnected, total=%d", len(_connected_clients))
