import logging
from datetime import datetime, timezone

from backend.compute.solana_liquidity import compute_quality, assess_congestion

logger = logging.getLogger(__name__)


class JupiterAgent:

    def __init__(
        self,
        quote_stale_seconds: float = 30.0,
        route_complexity_warn: int = 3,
        price_impact_warn_bps: float = 50.0,
        slippage_high_bps: float = 80.0,
        congestion_rpc_thresh_ms: float = 1500.0,
    ):
        self.quote_stale_seconds = quote_stale_seconds
        self.route_complexity_warn = route_complexity_warn
        self.price_impact_warn_bps = price_impact_warn_bps
        self.slippage_high_bps = slippage_high_bps
        self.congestion_rpc_thresh_ms = congestion_rpc_thresh_ms

    def evaluate(self, state: dict) -> list[dict]:
        signals = []
        now = datetime.now(timezone.utc).isoformat()
        data_ts = state.get("data_ts", now)

        quote_age_seconds = state.get("quote_age_seconds", 0)
        if quote_age_seconds > self.quote_stale_seconds:
            staleness_ratio = min(quote_age_seconds / self.quote_stale_seconds, 3.0)
            confidence = min(0.70 + staleness_ratio * 0.08, 0.95)
            signals.append({
                "type": "AGENT_SIGNAL",
                "agent": "jupiter_agent",
                "signal": "JUPITER_QUOTE_STALE",
                "direction": "neutral",
                "confidence": round(confidence, 2),
                "reason": f"Jupiter quote age {quote_age_seconds:.0f}s exceeds {self.quote_stale_seconds:.0f}s threshold - re-quote before execution",
                "severity": "high" if quote_age_seconds > self.quote_stale_seconds * 2 else "medium",
                "data_ts_used": data_ts,
                "ts": now,
                "proposed_action": "block_execution",
            })

        route_hops = state.get("route_hops", 1)
        if route_hops >= self.route_complexity_warn:
            confidence = min(0.70 + (route_hops - self.route_complexity_warn) * 0.10, 0.95)
            signals.append({
                "type": "AGENT_SIGNAL",
                "agent": "jupiter_agent",
                "signal": "JUPITER_ROUTE_COMPLEX",
                "direction": "neutral",
                "confidence": round(confidence, 2),
                "reason": f"Route uses {route_hops} hops - increased slippage and failure risk",
                "severity": "medium" if route_hops <= 4 else "high",
                "data_ts_used": data_ts,
                "ts": now,
                "proposed_action": "reduce_size",
            })

        price_impact_bps = state.get("price_impact_bps", 0)
        if price_impact_bps > self.price_impact_warn_bps:
            ratio = min(price_impact_bps / self.price_impact_warn_bps, 4.0)
            confidence = min(0.70 + ratio * 0.06, 0.95)
            severity = "high" if price_impact_bps > self.price_impact_warn_bps * 2 else "medium"
            signals.append({
                "type": "AGENT_SIGNAL",
                "agent": "jupiter_agent",
                "signal": "JUPITER_PRICE_IMPACT_HIGH",
                "direction": "bearish",
                "confidence": round(confidence, 2),
                "reason": f"Price impact {price_impact_bps:.1f}bps exceeds {self.price_impact_warn_bps:.0f}bps warn level",
                "severity": severity,
                "data_ts_used": data_ts,
                "ts": now,
                "proposed_action": "reduce_size" if severity == "medium" else "block_execution",
            })

        spread_bps = state.get("spread_bps", 0)
        if spread_bps > self.slippage_high_bps:
            ratio = min(spread_bps / self.slippage_high_bps, 4.0)
            confidence = min(0.70 + ratio * 0.06, 0.95)
            signals.append({
                "type": "AGENT_SIGNAL",
                "agent": "jupiter_agent",
                "signal": "JUPITER_SLIPPAGE_SPIKE",
                "direction": "neutral",
                "confidence": round(confidence, 2),
                "reason": f"Effective spread {spread_bps:.1f}bps indicates high slippage environment",
                "severity": "high" if spread_bps > self.slippage_high_bps * 2 else "medium",
                "data_ts_used": data_ts,
                "ts": now,
                "proposed_action": "delay_execution",
            })

        rpc_latency_ms = state.get("rpc_latency_ms", 0)
        slot_delta = state.get("slot_delta", 0)
        if rpc_latency_ms > 0 or slot_delta > 0:
            congestion = assess_congestion(
                rpc_latency_ms=rpc_latency_ms,
                slot_delta=slot_delta,
            )
            if congestion.get("congested"):
                severity = congestion.get("severity", "medium")
                confidence = 0.85 if severity == "high" else 0.75
                reasons = congestion.get("reasons", [])
                signals.append({
                    "type": "AGENT_SIGNAL",
                    "agent": "jupiter_agent",
                    "signal": "SOLANA_CONGESTION_WARNING",
                    "direction": "neutral",
                    "confidence": confidence,
                    "reason": f"Solana congestion detected: {'; '.join(reasons)}",
                    "severity": severity,
                    "data_ts_used": data_ts,
                    "ts": now,
                    "proposed_action": congestion.get("recommended_action", "delay_execution"),
                })

        ob_depth = state.get("ob_depth", 0)
        if spread_bps > 0 or price_impact_bps > 0 or rpc_latency_ms > 0:
            quality = compute_quality(
                spread_bps=spread_bps,
                price_impact_bps=price_impact_bps,
                rpc_latency_ms=rpc_latency_ms,
                ob_depth=ob_depth,
            )
            eq_score = quality.get("execution_quality_score", 50.0)
            if eq_score < 40.0:
                confidence = min(0.70 + (40.0 - eq_score) / 40.0 * 0.25, 0.95)
                signals.append({
                    "type": "AGENT_SIGNAL",
                    "agent": "jupiter_agent",
                    "signal": "JUPITER_LOW_QUALITY",
                    "direction": "neutral",
                    "confidence": round(confidence, 2),
                    "reason": f"Execution quality score {eq_score:.0f}/100 - poor conditions for swap",
                    "severity": "high" if eq_score < 20 else "medium",
                    "data_ts_used": data_ts,
                    "ts": now,
                    "proposed_action": "block_execution" if eq_score < 20 else "reduce_size",
                    "execution_quality": quality,
                })

        return signals
