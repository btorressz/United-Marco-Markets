import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class MacroAgent:

    def evaluate(self, state: dict) -> list[dict]:
        signals = []
        now = datetime.now(timezone.utc).isoformat()
        data_ts = state.get("data_ts", now)

        tariff_index = state.get("tariff_index", 0)
        tariff_momentum = state.get("tariff_momentum", 0)
        shock_score = state.get("shock_score", 0)

        if tariff_momentum > 5.0:
            signals.append({
                "type": "AGENT_SIGNAL",
                "agent": "macro_agent",
                "signal": "TARIFF_ACCELERATION",
                "reason": f"Tariff momentum {tariff_momentum:.2f} - rapid policy tightening detected",
                "weight_adjustment": {"shock_score": 1.3, "tariff_momentum": 1.5},
                "severity": "medium",
                "confidence": 0.75,
                "data_ts_used": data_ts,
                "ts": now,
            })

        if shock_score > 2.0:
            signals.append({
                "type": "AGENT_SIGNAL",
                "agent": "macro_agent",
                "signal": "NEWS_SHOCK_HIGH",
                "reason": f"Shock score {shock_score:.2f} - significant geopolitical event detected",
                "weight_adjustment": {"shock_score": 1.5},
                "severity": "high",
                "confidence": 0.80,
                "data_ts_used": data_ts,
                "ts": now,
            })

        if tariff_index > 70:
            signals.append({
                "type": "AGENT_SIGNAL",
                "agent": "macro_agent",
                "signal": "HIGH_TARIFF_REGIME",
                "reason": f"Tariff index at {tariff_index:.1f} - elevated trade risk environment",
                "severity": "medium",
                "confidence": 0.70,
                "data_ts_used": data_ts,
                "ts": now,
            })

        return signals
