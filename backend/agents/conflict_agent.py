from __future__ import annotations
from backend.agents.geopolitical_agent import _signal

class ConflictAgent:
    name = "conflict_agent"
    def evaluate(self, state=None):
        s = state or {}
        score = float(s.get("conflict_score", 0) or 0)
        signals = []
        if score >= 55:
            signals.append(_signal(self.name, "CONFLICT_ESCALATION_WARNING", min(.92, .52 + score / 220), "high" if score >= 70 else "medium", "bearish", "hedge_conflict_sensitive_assets", f"Conflict escalation score {score:.1f}", ["USO", "XLE", "ITA", "GLD", "SMH"], ["Middle East", "Taiwan Strait", "Russia/Ukraine"], s.get("data_quality", "degraded"), s.get("timestamp")))
        regions = s.get("regional_breakdown") or {}
        if any("Taiwan" in k for k in regions):
            signals.append(_signal(self.name, "TAIWAN_SEMICONDUCTOR_RISK", .74, "medium", "bearish", "review_semiconductor_exposure", "Taiwan Strait hotspot contributes to semiconductor supply-chain risk", ["SMH", "SOXX", "QQQ", "AAPL", "NVDA", "AMD"], ["Taiwan Strait"], s.get("data_quality", "degraded"), s.get("timestamp")))
        return signals
