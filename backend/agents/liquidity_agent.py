import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class LiquidityAgent:

    def evaluate(self, state: dict) -> list[dict]:
        signals = []
        now = datetime.now(timezone.utc).isoformat()
        data_ts = state.get("data_ts", now)

        stable_health = state.get("stablecoin_health", {})
        for symbol, data in stable_health.items():
            if isinstance(data, dict):
                depeg = data.get("depeg_bps", 0)
                if depeg > 50:
                    signals.append({
                        "type": "AGENT_SIGNAL",
                        "agent": "liquidity_agent",
                        "signal": "STABLE_DEPEG_DETECTED",
                        "reason": f"{symbol} depeg at {depeg:.0f}bps - monitor peg health",
                        "severity": "high",
                        "confidence": 0.90,
                        "data_ts_used": data_ts,
                        "ts": now,
                    })

        ob_imbalance = state.get("orderbook_imbalance", 0)
        if abs(ob_imbalance) > 0.5:
            direction = "buy-heavy" if ob_imbalance > 0 else "sell-heavy"
            signals.append({
                "type": "AGENT_SIGNAL",
                "agent": "liquidity_agent",
                "signal": "EXTREME_IMBALANCE",
                "reason": f"Orderbook heavily {direction} (imbalance={ob_imbalance:.2f})",
                "severity": "medium",
                "confidence": 0.75,
                "data_ts_used": data_ts,
                "ts": now,
            })

        spread_bps = state.get("spread_bps", 0)
        if spread_bps > 30:
            signals.append({
                "type": "AGENT_SIGNAL",
                "agent": "liquidity_agent",
                "signal": "WIDE_SPREAD",
                "reason": f"Spread {spread_bps:.0f}bps - liquidity thinning",
                "severity": "medium",
                "confidence": 0.80,
                "data_ts_used": data_ts,
                "ts": now,
            })

        return signals
