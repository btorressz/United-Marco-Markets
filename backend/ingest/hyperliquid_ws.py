import asyncio
import json
import logging
from datetime import datetime, timezone

import websockets

from backend.core.models import PriceTick, FundingTick, OrderbookSnap
from backend.core.state_store import StateStore

logger = logging.getLogger(__name__)

HYPERLIQUID_WS_URL = "wss://api.hyperliquid.xyz/ws"
MAX_RECONNECT_DELAY = 60
INITIAL_RECONNECT_DELAY = 1


class HyperliquidWSClient:

    def __init__(self, state_store: StateStore | None = None, symbol: str = "SOL"):
        self.state_store = state_store or StateStore()
        self.symbol = symbol
        self._ws = None
        self._running = False
        self._reconnect_delay = INITIAL_RECONNECT_DELAY

    async def start(self) -> None:
        self._running = True
        while self._running:
            try:
                await self._connect_and_listen()
            except Exception:
                if not self._running:
                    break
                logger.warning(
                    "Hyperliquid WS disconnected, reconnecting in %ds",
                    self._reconnect_delay,
                    exc_info=True,
                )
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, MAX_RECONNECT_DELAY)

    def stop(self) -> None:
        self._running = False
        if self._ws:
            asyncio.ensure_future(self._ws.close())

    async def _connect_and_listen(self) -> None:
        async with websockets.connect(HYPERLIQUID_WS_URL, ping_interval=20) as ws:
            self._ws = ws
            self._reconnect_delay = INITIAL_RECONNECT_DELAY
            logger.info("Connected to Hyperliquid WS")

            await self._subscribe(ws)

            async for raw_msg in ws:
                if not self._running:
                    break
                try:
                    msg = json.loads(raw_msg)
                    await self._handle_message(msg)
                except json.JSONDecodeError:
                    logger.warning("Hyperliquid WS: invalid JSON received")
                except Exception:
                    logger.warning("Hyperliquid WS: error handling message", exc_info=True)

    async def _subscribe(self, ws) -> None:
        subscriptions = [
            {"method": "subscribe", "subscription": {"type": "allMids"}},
            {"method": "subscribe", "subscription": {"type": "trades", "coin": self.symbol}},
            {"method": "subscribe", "subscription": {"type": "l2Book", "coin": self.symbol}},
        ]
        for sub in subscriptions:
            await ws.send(json.dumps(sub))
            logger.info("Hyperliquid WS subscribed: %s", sub["subscription"]["type"])

    async def _handle_message(self, msg: dict) -> None:
        channel = msg.get("channel", "")
        data = msg.get("data", {})

        if channel == "allMids":
            self._handle_all_mids(data)
        elif channel == "trades":
            self._handle_trades(data)
        elif channel == "l2Book":
            self._handle_l2_book(data)

    def _handle_all_mids(self, data: dict) -> None:
        mids = data.get("mids", {})
        price_str = mids.get(self.symbol)
        if price_str is None:
            return
        try:
            price = float(price_str)
        except (ValueError, TypeError):
            return

        tick = PriceTick(
            symbol=f"{self.symbol}/USD",
            venue="hyperliquid",
            price=price,
            ts=datetime.now(timezone.utc),
        )
        self.state_store.set_snapshot(
            f"price:hyperliquid:{self.symbol}/USD",
            tick.model_dump(mode="json"),
            ttl=60,
        )

    def _handle_trades(self, data) -> None:
        trades = data if isinstance(data, list) else [data]
        for trade in trades:
            coin = trade.get("coin", "")
            if coin != self.symbol:
                continue
            try:
                price = float(trade.get("px", 0))
            except (ValueError, TypeError):
                continue
            if price <= 0:
                continue

            tick = PriceTick(
                symbol=f"{coin}/USD",
                venue="hyperliquid",
                price=price,
                ts=datetime.now(timezone.utc),
            )
            self.state_store.set_snapshot(
                f"price:hyperliquid:trade:{coin}",
                tick.model_dump(mode="json"),
                ttl=60,
            )

    def _handle_l2_book(self, data: dict) -> None:
        coin = data.get("coin", self.symbol)
        levels = data.get("levels", [[], []])
        bids_raw = levels[0] if len(levels) > 0 else []
        asks_raw = levels[1] if len(levels) > 1 else []

        bids = [[float(b.get("px", 0)), float(b.get("sz", 0))] for b in bids_raw]
        asks = [[float(a.get("px", 0)), float(a.get("sz", 0))] for a in asks_raw]

        snap = OrderbookSnap(
            venue="hyperliquid",
            market=f"{coin}-PERP",
            bids=bids,
            asks=asks,
            ts=datetime.now(timezone.utc),
        )
        self.state_store.set_snapshot(
            f"orderbook:hyperliquid:{coin}",
            snap.model_dump(mode="json"),
            ttl=30,
        )
