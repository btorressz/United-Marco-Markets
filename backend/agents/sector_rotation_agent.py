from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class SectorRotationAgent:
    name = "sector_rotation_agent"

    def evaluate(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        sector_returns: dict[str, list[float]] = {}
        for r in rows:
            sector_returns.setdefault(r.get("sector", "Unknown"), []).append(float(r.get("return_5d", 0.0)))
        signals = []
        for sector, vals in sector_returns.items():
            avg = sum(vals) / len(vals) if vals else 0.0
            if avg <= -0.025:
                signals.append({
                    "agent": self.name,
                    "ticker": sector,
                    "signal": "SECTOR_ROTATION_WARNING",
                    "confidence": min(0.9, 0.6 + abs(avg) * 4),
                    "severity": "medium" if avg > -0.05 else "high",
                    "direction": "bearish",
                    "proposed_action": "rebalance_review",
                    "reason": f"Average 5D return for {sector} is {avg:.2%}, indicating defensive rotation pressure",
                    "ts": now,
                    "data_ts_used": now,
                })
        return signals
