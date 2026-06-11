from __future__ import annotations
from datetime import datetime, timezone
from typing import Any


def _signal(agent: str, signal: str, confidence: float, severity: str, direction: str, action: str, reason: str, assets: list[str], regions: list[str], data_quality: str, data_ts: str | None = None) -> dict[str, Any]:
    return {"agent": agent, "signal": signal, "confidence": round(confidence, 3), "severity": severity, "direction": direction, "proposed_action": action, "reason": reason, "ts": datetime.now(timezone.utc).isoformat(), "data_ts_used": data_ts or datetime.now(timezone.utc).isoformat(), "affected_assets": assets, "affected_regions": regions, "data_quality": data_quality}


class GeopoliticalAgent:
    name = "geopolitical_agent"
    def evaluate(self, state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        s = state or {}
        score = float(s.get("overall_score", 0) or 0)
        if score >= 60:
            return [_signal(self.name, "GEOPOLITICAL_RISK_HIGH", min(.95, .55 + score / 200), s.get("regime", "high_risk"), "bearish", "reduce_risk_preview_protection", f"Geopolitical index is {score:.1f}", s.get("affected_assets", [])[:12], list((s.get("regional_breakdown") or {}).keys())[:6], s.get("data_quality", "degraded"), s.get("timestamp"))]
        return []
