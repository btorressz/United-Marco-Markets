import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class RiskAgent:

    def __init__(self, liq_distance_warn_pct: float = 8.0):
        self.liq_distance_warn_pct = liq_distance_warn_pct

    def evaluate(self, state: dict) -> list[dict]:
        signals = []
        now = datetime.now(timezone.utc).isoformat()
        data_ts = state.get("data_ts", now)

        positions = state.get("positions", [])
        for pos in positions:
            liq_price = pos.get("liq_price")
            entry_price = pos.get("entry_price", 0)
            current_price = state.get("current_price", entry_price)
            if liq_price and current_price > 0:
                distance_pct = abs(current_price - liq_price) / current_price * 100.0
                if distance_pct < self.liq_distance_warn_pct:
                    signals.append({
                        "type": "AGENT_SIGNAL",
                        "agent": "risk_agent",
                        "signal": "RISK_WARNING",
                        "reason": f"Liquidation distance {distance_pct:.1f}% < {self.liq_distance_warn_pct}% for {pos.get('market', 'unknown')}",
                        "severity": "high",
                        "confidence": 0.95,
                        "data_ts_used": data_ts,
                        "ts": now,
                    })

        tariff_shock = state.get("shock_score", 0)
        vol_regime = state.get("vol_regime", "normal")
        if tariff_shock > 1.5 and vol_regime in ("high", "extreme"):
            signals.append({
                "type": "AGENT_SIGNAL",
                "agent": "risk_agent",
                "signal": "THROTTLE_RECOMMENDED",
                "reason": f"High shock ({tariff_shock:.2f}) + {vol_regime} vol regime -> throttle recommended",
                "severity": "high",
                "confidence": 0.85,
                "data_ts_used": data_ts,
                "ts": now,
            })

        margin_usage = state.get("margin_usage", 0)
        if margin_usage > 0.5:
            signals.append({
                "type": "AGENT_SIGNAL",
                "agent": "risk_agent",
                "signal": "MARGIN_WARNING",
                "reason": f"Margin usage {margin_usage:.0%} approaching limit",
                "severity": "medium",
                "confidence": 0.90,
                "data_ts_used": data_ts,
                "ts": now,
            })

        return signals
