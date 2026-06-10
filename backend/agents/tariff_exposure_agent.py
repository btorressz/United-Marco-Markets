from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class TariffExposureAgent:
    name = "tariff_exposure_agent"

    def evaluate(self, exposure_scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        out = []
        for s in exposure_scores:
            score = float(s.get("score", 0.0))
            if score >= 60:
                out.append({
                    "agent": self.name,
                    "ticker": s.get("ticker"),
                    "signal": "EQUITY_TARIFF_RISK_HIGH",
                    "confidence": min(0.95, 0.55 + score / 200),
                    "severity": s.get("severity", "high"),
                    "direction": "bearish",
                    "proposed_action": "reduce_or_hedge_exposure",
                    "reason": "; ".join((s.get("reasoning") or [])[:3]),
                    "ts": now,
                    "data_ts_used": s.get("ts"),
                })
        return out
