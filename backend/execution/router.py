import logging
from datetime import datetime, timezone

from backend.config import EXECUTION_MODE
from backend.core.event_bus import EventBus, EventType
from backend.core.state_store import StateStore
from backend.compute.risk_engine import RiskEngine
from backend.agents.execution_agent import ExecutionAgent
from backend.execution.paper_exec import PaperExecutor
from backend.execution.hyperliquid_exec import HyperliquidExecutor
from backend.execution.drift_exec import DriftExecutor

logger = logging.getLogger(__name__)


class ExecutionRouter:

    def __init__(self, event_bus: EventBus | None = None, risk_engine: RiskEngine | None = None):
        self.event_bus = event_bus or EventBus()
        self.risk_engine = risk_engine or RiskEngine()
        self.mode = EXECUTION_MODE
        self._store = StateStore()
        self._exec_agent = ExecutionAgent()

        self.paper = PaperExecutor(event_bus=self.event_bus)

        self.hyperliquid: HyperliquidExecutor | None = None
        self.drift: DriftExecutor | None = None

        if self.mode == "live":
            try:
                self.hyperliquid = HyperliquidExecutor(event_bus=self.event_bus)
            except Exception as exc:
                logger.error("Failed to init HyperliquidExecutor: %s", exc, exc_info=True)

            try:
                self.drift = DriftExecutor(event_bus=self.event_bus)
            except Exception as exc:
                logger.error("Failed to init DriftExecutor: %s", exc, exc_info=True)

        logger.info("ExecutionRouter initialised mode=%s", self.mode)

    def _get_data_context(self) -> dict:
        ctx = {"execution_mode": self.mode}
        now = datetime.now(timezone.utc)

        idx = self._store.get_snapshot("index:latest")
        if idx:
            ctx["tariff_ts"] = idx.get("ts", now.isoformat())
            ctx["shock_ts"] = idx.get("ts", now.isoformat())
        else:
            ctx["tariff_ts"] = now.isoformat()
            ctx["shock_ts"] = now.isoformat()

        price_snap = self._store.get_snapshot("price:pyth:SOL_USD")
        if price_snap:
            ctx["price_ts"] = price_snap.get("ts", now.isoformat())
            price_ts = price_snap.get("ts", now.isoformat())
            try:
                if isinstance(price_ts, str):
                    pt = datetime.fromisoformat(price_ts)
                    ctx["data_age_ms"] = int((now - pt).total_seconds() * 1000)
            except Exception:
                pass
        else:
            ctx["price_ts"] = now.isoformat()

        integrity = self._store.get_snapshot("price:integrity")
        if integrity:
            ctx["price_integrity_status"] = integrity.get("status", "OK")
        else:
            ctx["price_integrity_status"] = "OK"

        return ctx

    def _get_market_state(self) -> dict:
        ms = {}
        micro = self._store.get_snapshot("microstructure:latest")
        if micro:
            ms["spread_bps"] = micro.get("spread_bps", 0)
            ms["liquidity_depth"] = micro.get("liquidity_depth", 0)
        integrity = self._store.get_snapshot("price:integrity")
        if integrity:
            ms["price_integrity"] = integrity.get("status", "OK")
        else:
            ms["price_integrity"] = "OK"
        return ms

    def route_order(
        self,
        venue: str,
        market: str,
        side: str,
        size: float,
        price: float | None = None,
    ) -> dict:
        now = datetime.now(timezone.utc)
        data_ctx = self._get_data_context()

        positions = self.paper.get_positions()
        proposed = {
            "venue": venue,
            "market": market,
            "side": side,
            "size": size,
            "price": price or 0.0,
        }

        allowed, reasons = self.risk_engine.check_constraints(positions, proposed)
        if not allowed:
            self.event_bus.emit(
                EventType.RISK_THROTTLE_ON,
                source="execution_router",
                payload={**data_ctx, "reasons": reasons, "proposed": proposed},
            )
            logger.warning("Order blocked by risk engine: %s", reasons)
            return {
                "status": "blocked",
                "reasons": reasons,
                **data_ctx,
                "ts": now.isoformat(),
            }

        if self.mode == "live":
            market_state = self._get_market_state()
            check = self._exec_agent.pre_trade_check(proposed, market_state)
            if not check.get("allowed", True):
                self.event_bus.emit(
                    EventType.AGENT_BLOCKED,
                    source="execution_agent",
                    payload={
                        **data_ctx,
                        "reasons": check.get("reasons", []),
                        "proposed": proposed,
                        "message": "Trade blocked by execution agent: " + "; ".join(check.get("reasons", [])),
                    },
                )
                logger.warning("Order blocked by execution agent: %s", check.get("reasons"))
                return {
                    "status": "agent_blocked",
                    "reasons": check.get("reasons", []),
                    **data_ctx,
                    "ts": now.isoformat(),
                }

        if self.mode == "paper":
            result = self.paper.place_order(
                venue=venue, market=market, side=side, size=size, price=price,
                data_context=data_ctx,
            )
            result["execution_mode"] = "paper"
            return result

        executor = self._get_live_executor(venue)
        if executor is None:
            logger.warning("No live executor for venue=%s, falling back to paper", venue)
            result = self.paper.place_order(
                venue=venue, market=market, side=side, size=size, price=price,
                data_context=data_ctx,
            )
            result["execution_mode"] = "paper_fallback"
            return result

        try:
            result = executor.place_order(
                market=market, side=side, size=size, price=price or 0.0,
            )
            result["execution_mode"] = "live"
            result["venue"] = venue
            result.update(data_ctx)
            return result
        except Exception as exc:
            logger.error("Live execution failed for %s, falling back to paper: %s", venue, exc, exc_info=True)
            result = self.paper.place_order(
                venue=venue, market=market, side=side, size=size, price=price,
                data_context=data_ctx,
            )
            result["execution_mode"] = "paper_fallback"
            return result

    def _get_live_executor(self, venue: str):
        venue_lower = venue.lower()
        if venue_lower == "hyperliquid" and self.hyperliquid and self.hyperliquid.enabled:
            return self.hyperliquid
        if venue_lower == "drift" and self.drift and self.drift.enabled:
            return self.drift
        return None

    def get_all_positions(self) -> list[dict]:
        positions = list(self.paper.get_positions())

        if self.mode == "live":
            if self.hyperliquid and self.hyperliquid.enabled:
                try:
                    positions.extend(self.hyperliquid.get_positions())
                except Exception as exc:
                    logger.error("Failed to get Hyperliquid positions: %s", exc)

            if self.drift and self.drift.enabled:
                try:
                    positions.extend(self.drift.get_positions())
                except Exception as exc:
                    logger.error("Failed to get Drift positions: %s", exc)

        return positions

    def get_status(self) -> dict:
        return {
            "execution_mode": self.mode,
            "paper_enabled": self.paper.enabled,
            "hyperliquid_enabled": self.hyperliquid.enabled if self.hyperliquid else False,
            "drift_enabled": self.drift.enabled if self.drift else False,
            "risk_status": self.risk_engine.get_status(),
        }
