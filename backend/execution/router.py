import logging
from datetime import datetime, timezone

from backend.config import EXECUTION_MODE, PRICE_FRESHNESS_THRESHOLD_S, PRICE_INTEGRITY_BLOCK_LIVE
from backend.core.event_bus import EventBus, EventType
from backend.core.state_store import StateStore
from backend.core.price_authority import PriceAuthority
from backend.compute.risk_engine import RiskEngine
from backend.agents.execution_agent import ExecutionAgent
from backend.execution.paper_exec import PaperExecutor
from backend.execution.hyperliquid_exec import HyperliquidExecutor
from backend.execution.drift_exec import DriftExecutor

logger = logging.getLogger(__name__)


def _symbol_from_market(market: str) -> str:
    m = market.upper().replace("-PERP", "_USD").replace("/", "_")
    if not m.endswith("_USD") and not m.endswith("_USDC") and not m.endswith("_USDT"):
        m = m.split("-")[0].split("/")[0] + "_USD"
    return m


class ExecutionRouter:

    def __init__(self, event_bus: EventBus | None = None, risk_engine: RiskEngine | None = None):
        self.event_bus = event_bus or EventBus()
        self.risk_engine = risk_engine or RiskEngine()
        self.mode = EXECUTION_MODE
        self._store = StateStore()
        self._price_authority = PriceAuthority(state_store=self._store)
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

    def _get_live_price(self, market: str) -> dict:
        symbol = _symbol_from_market(market)
        result = self._price_authority.get_price(symbol)
        now = datetime.now(timezone.utc)

        if not result.found or result.price <= 0:
            return {
                "price": 0.0,
                "source": "none",
                "ts": now.isoformat(),
                "age_s": 0,
                "fresh": False,
                "found": False,
            }

        age_s = (now - result.ts).total_seconds()
        fresh = age_s <= PRICE_FRESHNESS_THRESHOLD_S

        return {
            "price": result.price,
            "source": result.source,
            "ts": result.ts.isoformat(),
            "age_s": round(age_s, 1),
            "fresh": fresh,
            "found": True,
        }

    def _get_data_context(self, live_price: dict | None = None) -> dict:
        ctx = {"execution_mode": self.mode}
        now = datetime.now(timezone.utc)

        idx = self._store.get_snapshot("index:latest")
        if idx:
            ctx["tariff_ts"] = idx.get("ts", now.isoformat())
            ctx["shock_ts"] = idx.get("ts", now.isoformat())
        else:
            ctx["tariff_ts"] = now.isoformat()
            ctx["shock_ts"] = now.isoformat()

        if live_price and live_price.get("found"):
            ctx["price_ts"] = live_price["ts"]
            ctx["price_source"] = live_price["source"]
            ctx["price_asof_ts"] = live_price["ts"]
            ctx["data_age_ms"] = int(live_price["age_s"] * 1000)
        else:
            price_snap = self._store.get_snapshot("price:pyth:SOL_USD")
            if price_snap:
                ctx["price_ts"] = price_snap.get("ts", now.isoformat())
                ctx["price_source"] = "pyth"
                price_ts = price_snap.get("ts", now.isoformat())
                try:
                    if isinstance(price_ts, str):
                        pt = datetime.fromisoformat(price_ts)
                        ctx["data_age_ms"] = int((now - pt).total_seconds() * 1000)
                except Exception:
                    pass
            else:
                ctx["price_ts"] = now.isoformat()
                ctx["price_source"] = "none"

        integrity = self._store.get_snapshot("price:integrity")
        if integrity:
            ctx["integrity_status"] = integrity.get("status", "OK")
        else:
            ctx["integrity_status"] = "OK"

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

        live_price_info = self._get_live_price(market)
        fill_price = price if price is not None and price > 0 else live_price_info.get("price", 0.0)

        data_ctx = self._get_data_context(live_price_info)

        if not live_price_info.get("found") and fill_price <= 0:
            self.event_bus.emit(
                EventType.TRADE_BLOCKED_STALE_DATA,
                source="execution_router",
                payload={
                    **data_ctx,
                    "reason": "No price data available for " + market,
                    "market": market,
                    "side": side,
                },
            )
            return {
                "status": "blocked",
                "reasons": ["No price data available — try again when feeds are active"],
                **data_ctx,
                "ts": now.isoformat(),
            }

        if not live_price_info.get("fresh", True) and live_price_info.get("found"):
            age_s = live_price_info.get("age_s", 0)
            if self.mode == "live":
                self.event_bus.emit(
                    EventType.TRADE_BLOCKED_STALE_DATA,
                    source="execution_router",
                    payload={
                        **data_ctx,
                        "reason": f"Price data stale ({age_s:.0f}s old, threshold {PRICE_FRESHNESS_THRESHOLD_S}s)",
                        "market": market,
                        "side": side,
                        "age_s": age_s,
                    },
                )
                return {
                    "status": "blocked",
                    "reasons": [f"Price data stale ({age_s:.0f}s old) — refresh and try again"],
                    **data_ctx,
                    "ts": now.isoformat(),
                }
            else:
                data_ctx["data_quality"] = "DEGRADED"
                self.event_bus.emit(
                    EventType.TRADE_DEGRADED_DATA,
                    source="execution_router",
                    payload={
                        **data_ctx,
                        "reason": f"Paper trade with stale data ({age_s:.0f}s old)",
                        "market": market,
                        "side": side,
                    },
                )

        integrity_status = data_ctx.get("integrity_status", "OK")
        if integrity_status == "WARNING":
            if self.mode == "live" and PRICE_INTEGRITY_BLOCK_LIVE:
                self.event_bus.emit(
                    EventType.TRADE_BLOCKED_STALE_DATA,
                    source="execution_router",
                    payload={
                        **data_ctx,
                        "reason": "Price integrity WARNING — cross-venue deviation too high",
                        "market": market,
                        "side": side,
                    },
                )
                return {
                    "status": "blocked",
                    "reasons": ["Price integrity WARNING — cross-venue deviation too high"],
                    **data_ctx,
                    "ts": now.isoformat(),
                }
            else:
                data_ctx["data_quality"] = data_ctx.get("data_quality", "DEGRADED")
                self.event_bus.emit(
                    EventType.TRADE_DEGRADED_DATA,
                    source="execution_router",
                    payload={
                        **data_ctx,
                        "reason": "Paper trade with integrity WARNING",
                        "market": market,
                        "side": side,
                    },
                )

        positions = self.paper.get_positions()
        proposed = {
            "venue": venue,
            "market": market,
            "side": side,
            "size": size,
            "price": fill_price,
        }

        allowed, reasons = self.risk_engine.check_constraints(positions, proposed, execution_mode=self.mode)
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
                venue=venue, market=market, side=side, size=size, price=fill_price,
                data_context=data_ctx,
            )
            result["execution_mode"] = "paper"
            return result

        executor = self._get_live_executor(venue)
        if executor is None:
            logger.warning("No live executor for venue=%s, falling back to paper", venue)
            result = self.paper.place_order(
                venue=venue, market=market, side=side, size=size, price=fill_price,
                data_context=data_ctx,
            )
            result["execution_mode"] = "paper_fallback"
            return result

        try:
            result = executor.place_order(
                market=market, side=side, size=size, price=fill_price,
            )
            result["execution_mode"] = "live"
            result["venue"] = venue
            result.update(data_ctx)
            return result
        except Exception as exc:
            logger.error("Live execution failed for %s, falling back to paper: %s", venue, exc, exc_info=True)
            result = self.paper.place_order(
                venue=venue, market=market, side=side, size=size, price=fill_price,
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

