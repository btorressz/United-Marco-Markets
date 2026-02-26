import uuid
import logging
from datetime import datetime, timezone

from backend.core.event_bus import EventBus, EventType
from backend.core.models import PositionState

logger = logging.getLogger(__name__)


class PaperExecutor:

    def __init__(self, event_bus: EventBus | None = None):
        self.event_bus = event_bus or EventBus()
        self._positions: dict[str, dict] = {}
        self._orders: dict[str, dict] = {}
        self.enabled = True
        logger.info("PaperExecutor initialised (paper mode)")

    def place_order(
        self,
        venue: str,
        market: str,
        side: str,
        size: float,
        order_type: str = "limit",
        price: float | None = None,
        data_context: dict | None = None,
    ) -> dict:
        order_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        fill_price = price if price is not None and price > 0 else 0.0
        ctx = data_context or {}

        self.event_bus.emit(
            EventType.ORDER_SENT,
            source="paper_executor",
            payload={
                "order_id": order_id,
                "venue": venue,
                "market": market,
                "side": side,
                "size": size,
                "order_type": order_type,
                "price": fill_price,
                "tariff_ts": ctx.get("tariff_ts"),
                "shock_ts": ctx.get("shock_ts"),
                "price_ts": ctx.get("price_ts"),
                "price_source": ctx.get("price_source", "unknown"),
                "price_asof_ts": ctx.get("price_asof_ts"),
                "integrity_status": ctx.get("integrity_status", "OK"),
                "execution_mode": ctx.get("execution_mode", "paper"),
                "data_age_ms": ctx.get("data_age_ms"),
                "data_quality": ctx.get("data_quality", "OK"),
                "message": f"Paper {side.upper()} {size} {market} @ {fill_price:.4f}",
            },
        )

        self._orders[order_id] = {
            "order_id": order_id,
            "venue": venue,
            "market": market,
            "side": side,
            "size": size,
            "order_type": order_type,
            "price": fill_price,
            "status": "paper_filled",
            "fill_price": fill_price,
            "ts": now.isoformat(),
        }

        self._update_position(venue, market, side, size, fill_price)

        self.event_bus.emit(
            EventType.ORDER_FILLED,
            source="paper_executor",
            payload={
                "order_id": order_id,
                "venue": venue,
                "market": market,
                "side": side,
                "size": size,
                "fill_price": fill_price,
                "tariff_ts": ctx.get("tariff_ts"),
                "shock_ts": ctx.get("shock_ts"),
                "price_ts": ctx.get("price_ts"),
                "price_source": ctx.get("price_source", "unknown"),
                "price_asof_ts": ctx.get("price_asof_ts"),
                "integrity_status": ctx.get("integrity_status", "OK"),
                "execution_mode": ctx.get("execution_mode", "paper"),
                "data_age_ms": ctx.get("data_age_ms"),
                "data_quality": ctx.get("data_quality", "OK"),
                "message": f"Paper {side.upper()} {size} {market} filled @ {fill_price:.4f}",
            },
        )

        logger.info(
            "Paper order filled: %s %s %s size=%.4f price=%.4f id=%s",
            venue, market, side, size, fill_price, order_id,
        )

        return {
            "order_id": order_id,
            "status": "paper_filled",
            "fill_price": fill_price,
            "side": side,
            "market": market,
            "venue": venue,
            "size": size,
            "ts": now.isoformat(),
        }

    def cancel_order(self, order_id: str) -> dict:
        if order_id in self._orders:
            self._orders[order_id]["status"] = "cancelled"
            logger.info("Paper order cancelled: %s", order_id)
            return {"order_id": order_id, "status": "cancelled"}
        logger.warning("Paper cancel: order %s not found", order_id)
        return {"order_id": order_id, "status": "not_found"}

    def get_positions(self) -> list[dict]:
        results = []
        for key, pos in self._positions.items():
            size = pos["size"]
            side = "long" if size > 0 else "short"
            results.append(
                PositionState(
                    venue=pos["venue"],
                    market=pos["market"],
                    size=size,
                    entry_price=pos["entry_price"],
                    pnl=pos.get("pnl", 0.0),
                    margin=pos.get("margin", 0.0),
                ).model_dump() | {"side": side}
            )
        return results

    def _update_position(self, venue: str, market: str, side: str, size: float, price: float) -> None:
        key = f"{venue}:{market}"
        signed_size = size if side.lower() == "buy" else -size

        if key in self._positions:
            existing = self._positions[key]
            old_size = existing["size"]
            old_entry = existing["entry_price"]

            new_size = old_size + signed_size

            if abs(new_size) < 1e-12:
                del self._positions[key]
                return

            if (old_size > 0 and signed_size > 0) or (old_size < 0 and signed_size < 0):
                total_cost = abs(old_size) * old_entry + abs(signed_size) * price
                new_entry = total_cost / abs(new_size) if abs(new_size) > 0 else price
            else:
                new_entry = old_entry if abs(new_size) >= abs(old_size) else price

            existing["size"] = new_size
            existing["entry_price"] = new_entry
        else:
            self._positions[key] = {
                "venue": venue,
                "market": market,
                "size": signed_size,
                "entry_price": price,
                "pnl": 0.0,
                "margin": 0.0,
            }

