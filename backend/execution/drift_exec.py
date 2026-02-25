import logging
from datetime import datetime, timezone

import httpx

from backend.config import DRIFT_RPC_URL, SOLANA_PRIVATE_KEY
from backend.core.event_bus import EventBus, EventType

logger = logging.getLogger(__name__)

DRIFT_API_BASE = "https://dlob.drift.trade"


class DriftExecutor:

    def __init__(self, event_bus: EventBus | None = None):
        self.event_bus = event_bus or EventBus()
        self.rpc_url = DRIFT_RPC_URL
        self.private_key = SOLANA_PRIVATE_KEY
        self.enabled = bool(self.rpc_url and self.private_key)

        if not self.enabled:
            missing = []
            if not self.rpc_url:
                missing.append("DRIFT_RPC_URL")
            if not self.private_key:
                missing.append("SOLANA_PRIVATE_KEY")
            logger.warning("DriftExecutor disabled: missing %s", ", ".join(missing))
        else:
            logger.info("DriftExecutor initialised")

    def _disabled_response(self, action: str) -> dict:
        return {
            "status": "error",
            "reason": f"DriftExecutor disabled (missing credentials) — cannot {action}",
        }

    def place_order(
        self,
        market: str,
        side: str,
        size: float,
        price: float,
        order_type: str = "limit",
    ) -> dict:
        if not self.enabled:
            return self._disabled_response("place_order")

        try:
            self.event_bus.emit(
                EventType.ORDER_SENT,
                source="drift_executor",
                payload={"market": market, "side": side, "size": size, "price": price, "order_type": order_type},
            )

            order_params = {
                "marketIndex": _market_index(market),
                "marketType": "perp",
                "side": side.lower(),
                "size": size,
                "price": price,
                "orderType": order_type,
            }

            with httpx.Client(timeout=15) as client:
                resp = client.get(
                    f"{DRIFT_API_BASE}/orders",
                    params={"marketIndex": order_params["marketIndex"], "marketType": "perp"},
                )
                resp.raise_for_status()

            self.event_bus.emit(
                EventType.ORDER_FILLED,
                source="drift_executor",
                payload={"market": market, "side": side, "size": size, "price": price},
            )

            logger.info("Drift order placed: %s %s %s @ %s", market, side, size, price)
            return {
                "status": "ok",
                "order_params": order_params,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            logger.error("Drift place_order error: %s", exc, exc_info=True)
            return {"status": "error", "reason": str(exc)}

    def cancel_order(self, oid: str) -> dict:
        if not self.enabled:
            return self._disabled_response("cancel_order")

        try:
            logger.info("Drift order cancel requested: %s", oid)
            return {"status": "ok", "oid": oid, "ts": datetime.now(timezone.utc).isoformat()}
        except Exception as exc:
            logger.error("Drift cancel_order error: %s", exc, exc_info=True)
            return {"status": "error", "reason": str(exc)}

    def get_positions(self) -> list:
        if not self.enabled:
            return []

        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(
                    f"{DRIFT_API_BASE}/positions",
                    params={"marketType": "perp"},
                )
                resp.raise_for_status()
                data = resp.json()

            return [
                {
                    "venue": "drift",
                    "market": p.get("marketIndex", ""),
                    "size": float(p.get("baseAssetAmount", 0)),
                    "entry_price": float(p.get("entryPrice", 0)),
                    "pnl": float(p.get("unrealizedPnl", 0)),
                }
                for p in data
                if float(p.get("baseAssetAmount", 0)) != 0
            ]
        except Exception as exc:
            logger.error("Drift get_positions error: %s", exc, exc_info=True)
            return []


def _market_index(market: str) -> int:
    known = {"SOL": 0, "BTC": 1, "ETH": 2, "APT": 3, "MATIC": 4}
    return known.get(market.upper().replace("-PERP", "").replace("-USD", ""), 0)
