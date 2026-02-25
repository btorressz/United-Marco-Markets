import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ExecutionAgent:

    def __init__(self, max_slippage_bps: float = 50.0, min_liquidity_depth: float = 50.0):
        self.max_slippage_bps = max_slippage_bps
        self.min_liquidity_depth = min_liquidity_depth

    def pre_trade_check(self, order: dict, market_state: dict) -> dict:
        reasons = []
        allowed = True

        spread_bps = market_state.get("spread_bps", 0)
        if spread_bps > self.max_slippage_bps:
            reasons.append(f"Spread {spread_bps:.0f}bps exceeds max {self.max_slippage_bps:.0f}bps")
            allowed = False

        depth = market_state.get("liquidity_depth", 0)
        if 0 < depth < self.min_liquidity_depth:
            reasons.append(f"Liquidity depth {depth:.0f} below minimum {self.min_liquidity_depth:.0f}")
            allowed = False

        integrity = market_state.get("price_integrity", "OK")
        if integrity == "WARNING":
            reasons.append("Price integrity WARNING - cross-venue deviation detected")
            allowed = False

        result = {
            "allowed": allowed,
            "reasons": reasons,
            "order": order,
            "ts": datetime.now(timezone.utc).isoformat(),
        }

        if not allowed:
            result["type"] = "AGENT_BLOCKED"
            result["agent"] = "execution_agent"
        else:
            result["type"] = "AGENT_SIGNAL"
            result["agent"] = "execution_agent"
            result["signal"] = "TRADE_APPROVED"

        return result

    def evaluate(self, state: dict) -> list[dict]:
        signals = []
        now = datetime.now(timezone.utc).isoformat()
        data_ts = state.get("data_ts", now)

        integrity = state.get("price_integrity", "OK")
        if integrity == "WARNING":
            signals.append({
                "type": "AGENT_SIGNAL",
                "agent": "execution_agent",
                "signal": "PRICE_INTEGRITY_WARNING",
                "reason": "Price integrity compromised - execution should be paused",
                "severity": "high",
                "confidence": 0.95,
                "data_ts_used": data_ts,
                "ts": now,
            })

        spread_bps = state.get("spread_bps", 0)
        if spread_bps > self.max_slippage_bps:
            signals.append({
                "type": "AGENT_SIGNAL",
                "agent": "execution_agent",
                "signal": "HIGH_SLIPPAGE_WARNING",
                "reason": f"Spread {spread_bps:.0f}bps exceeds safe threshold {self.max_slippage_bps:.0f}bps",
                "severity": "medium",
                "confidence": 0.90,
                "data_ts_used": data_ts,
                "ts": now,
            })

        return signals
