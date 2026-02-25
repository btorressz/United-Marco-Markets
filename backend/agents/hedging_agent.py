import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class HedgingAgent:

    def __init__(
        self,
        high_shock_threshold: float = 60.0,
        high_vol_regimes: tuple = ("high", "extreme"),
        depeg_warn_bps: float = 30.0,
        margin_warn_threshold: float = 0.6,
        confidence_floor: float = 0.70,
    ):
        self.high_shock_threshold = high_shock_threshold
        self.high_vol_regimes = high_vol_regimes
        self.depeg_warn_bps = depeg_warn_bps
        self.margin_warn_threshold = margin_warn_threshold
        self.confidence_floor = confidence_floor

    def evaluate(self, state: dict) -> list[dict]:
        signals = []
        now = datetime.now(timezone.utc).isoformat()
        data_ts = state.get("data_ts", now)

        shock_score = state.get("shock_score", 0)
        tariff_index = state.get("tariff_index", 0)
        vol_regime = state.get("vol_regime", "normal")
        funding_regime = state.get("funding_regime", "neutral")
        margin_usage = state.get("margin_usage", 0)
        predictor_prob = state.get("predictor_prob", 0.5)
        carry_score = state.get("carry_score", 0)

        stable_health = state.get("stablecoin_health", {})
        max_depeg = 0.0
        if isinstance(stable_health, dict):
            for sym, info in stable_health.items():
                if isinstance(info, dict):
                    max_depeg = max(max_depeg, info.get("depeg_bps", 0))

        positions = state.get("positions", [])
        exposure = sum(abs(p.get("size", 0) * p.get("entry_price", 0)) for p in positions if isinstance(p, dict))

        target_beta = 1.0
        target_delta = 0.0
        urgency = "low"
        reasoning = []
        proposed_actions = []

        if shock_score > self.high_shock_threshold:
            reduction = min((shock_score - self.high_shock_threshold) / 100.0, 0.5)
            target_beta -= reduction
            reasoning.append(f"Shock score {shock_score:.1f} elevated — reduce beta by {reduction:.2f}")
            proposed_actions.append("reduce_exposure")
            urgency = "medium"

        if vol_regime in self.high_vol_regimes:
            target_beta *= 0.7
            reasoning.append(f"Vol regime '{vol_regime}' — scale to 70% target beta")
            proposed_actions.append("scale_down_risk")
            urgency = "high" if vol_regime == "extreme" else max(urgency, "medium")

        if predictor_prob < 0.35:
            target_delta = -0.15
            reasoning.append(f"Macro predictor bearish ({predictor_prob:.2f}) — tilt short delta")
            proposed_actions.append("hedge_via_hl_short")
        elif predictor_prob > 0.65:
            target_delta = 0.10
            reasoning.append(f"Macro predictor bullish ({predictor_prob:.2f}) — allow long delta")

        if max_depeg > self.depeg_warn_bps:
            target_beta *= 0.8
            reasoning.append(f"Stablecoin depeg {max_depeg:.0f}bps — reduce exposure + rotate to safer stables")
            proposed_actions.append("stable_rotation")
            urgency = "high"

        if margin_usage > self.margin_warn_threshold:
            target_beta *= 0.6
            reasoning.append(f"Margin usage {margin_usage:.0%} high — deleverage urgently")
            proposed_actions.append("deleverage")
            urgency = "high"

        if funding_regime == "negative" and carry_score < -0.05:
            reasoning.append(f"Negative funding regime (carry {carry_score:.3f}) — consider reducing HL longs or hedging via Drift")
            proposed_actions.append("hedge_funding_via_drift")

        if tariff_index > 70:
            target_beta *= 0.85
            reasoning.append(f"Tariff index {tariff_index:.1f} elevated — macro headwind, reduce risk")
            proposed_actions.append("reduce_exposure")

        if not reasoning:
            reasoning.append("No hedge triggers active — maintain current positioning")
            return signals

        target_beta = max(round(target_beta, 3), 0.0)
        target_delta = round(target_delta, 3)

        hedge_legs = []
        if "hedge_via_hl_short" in proposed_actions or "reduce_exposure" in proposed_actions:
            hedge_legs.append({"venue": "hyperliquid", "action": "short_perp", "sizing": "proportional_to_beta_gap"})
        if "hedge_funding_via_drift" in proposed_actions:
            hedge_legs.append({"venue": "drift", "action": "long_perp", "sizing": "carry_neutral"})
        if "stable_rotation" in proposed_actions:
            hedge_legs.append({"venue": "jupiter", "action": "swap_to_usdc", "sizing": "excess_stable_allocation"})

        confidence_factors = []
        if shock_score > 0:
            confidence_factors.append(min(shock_score / 100.0, 0.3))
        if vol_regime in self.high_vol_regimes:
            confidence_factors.append(0.15)
        if margin_usage > self.margin_warn_threshold:
            confidence_factors.append(0.10)
        if max_depeg > self.depeg_warn_bps:
            confidence_factors.append(0.10)

        confidence = min(self.confidence_floor + sum(confidence_factors), 0.95)

        signals.append({
            "type": "AGENT_SIGNAL",
            "agent": "hedging_agent",
            "signal": "HEDGE_PROPOSAL",
            "direction": "bearish" if target_delta < 0 else "bullish" if target_delta > 0 else "neutral",
            "confidence": round(confidence, 2),
            "reason": "; ".join(reasoning),
            "severity": urgency,
            "data_ts_used": data_ts,
            "ts": now,
            "proposed_action": proposed_actions[0] if proposed_actions else "monitor",
            "hedge_detail": {
                "target_beta": target_beta,
                "target_delta": target_delta,
                "urgency": urgency,
                "hedge_legs": hedge_legs,
                "all_proposed_actions": proposed_actions,
                "current_exposure": round(exposure, 2),
            },
        })

        if urgency == "high" and len(proposed_actions) >= 2:
            signals.append({
                "type": "AGENT_SIGNAL",
                "agent": "hedging_agent",
                "signal": "HEDGE_REBALANCE_SUGGESTED",
                "direction": "neutral",
                "confidence": round(confidence, 2),
                "reason": f"Multiple hedge triggers active ({len(proposed_actions)} actions) — rebalance recommended",
                "severity": "high",
                "data_ts_used": data_ts,
                "ts": now,
                "proposed_action": "rebalance",
            })

        if margin_usage > 0.8:
            signals.append({
                "type": "AGENT_SIGNAL",
                "agent": "hedging_agent",
                "signal": "HEDGE_THROTTLE_RECOMMENDED",
                "direction": "neutral",
                "confidence": 0.90,
                "reason": f"Margin usage {margin_usage:.0%} critical — throttle new positions until deleveraged",
                "severity": "high",
                "data_ts_used": data_ts,
                "ts": now,
                "proposed_action": "throttle",
            })

        return signals
