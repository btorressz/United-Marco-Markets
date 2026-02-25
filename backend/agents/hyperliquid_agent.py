import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class HyperliquidAgent:

    def __init__(
        self,
        imbalance_threshold: float = 0.4,
        spread_compress_bps: float = 5.0,
        aggression_threshold: float = 0.6,
        thinning_depth_threshold: float = 50000.0,
    ):
        self.imbalance_threshold = imbalance_threshold
        self.spread_compress_bps = spread_compress_bps
        self.aggression_threshold = aggression_threshold
        self.thinning_depth_threshold = thinning_depth_threshold

    def evaluate(self, state: dict) -> list[dict]:
        signals = []
        now = datetime.now(timezone.utc).isoformat()
        data_ts = state.get("data_ts", now)

        ob_imbalance = state.get("orderbook_imbalance", 0)
        spread_bps = state.get("spread_bps", 0)
        trade_aggression = state.get("trade_aggression", 0)
        bid_depth = state.get("bid_depth", 0)
        ask_depth = state.get("ask_depth", 0)
        total_depth = bid_depth + ask_depth

        if abs(ob_imbalance) > self.imbalance_threshold:
            direction = "bullish" if ob_imbalance > 0 else "bearish"
            confidence = min(0.70 + abs(ob_imbalance) * 0.25, 0.95)
            signals.append({
                "type": "AGENT_SIGNAL",
                "agent": "hyperliquid_agent",
                "signal": "MICROSTRUCTURE_SIGNAL",
                "direction": direction,
                "confidence": round(confidence, 2),
                "reason": f"Orderbook imbalance {ob_imbalance:.2f} suggests {direction} pressure",
                "severity": "medium",
                "data_ts_used": data_ts,
                "ts": now,
            })

        if 0 < spread_bps <= self.spread_compress_bps:
            confidence = min(0.70 + (self.spread_compress_bps - spread_bps) / self.spread_compress_bps * 0.20, 0.95)
            signals.append({
                "type": "AGENT_SIGNAL",
                "agent": "hyperliquid_agent",
                "signal": "MICROSTRUCTURE_SIGNAL",
                "direction": "neutral",
                "confidence": round(confidence, 2),
                "reason": f"Spread compressed to {spread_bps:.1f}bps - high liquidity regime",
                "severity": "low",
                "data_ts_used": data_ts,
                "ts": now,
            })

        if abs(trade_aggression) > self.aggression_threshold:
            direction = "bullish" if trade_aggression > 0 else "bearish"
            confidence = min(0.70 + abs(trade_aggression) * 0.20, 0.95)
            signals.append({
                "type": "AGENT_SIGNAL",
                "agent": "hyperliquid_agent",
                "signal": "MICROSTRUCTURE_SIGNAL",
                "direction": direction,
                "confidence": round(confidence, 2),
                "reason": f"Trade aggression {trade_aggression:.2f} indicates {direction} momentum",
                "severity": "medium",
                "data_ts_used": data_ts,
                "ts": now,
            })

        if 0 < total_depth < self.thinning_depth_threshold:
            thinning_ratio = total_depth / self.thinning_depth_threshold
            confidence = min(0.70 + (1.0 - thinning_ratio) * 0.25, 0.95)
            signals.append({
                "type": "AGENT_SIGNAL",
                "agent": "hyperliquid_agent",
                "signal": "LIQUIDITY_THINNING_WARNING",
                "direction": "neutral",
                "confidence": round(confidence, 2),
                "reason": f"Total depth ${total_depth:,.0f} below ${self.thinning_depth_threshold:,.0f} threshold",
                "severity": "high",
                "data_ts_used": data_ts,
                "ts": now,
            })

        return signals
