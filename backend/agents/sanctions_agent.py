from __future__ import annotations
from backend.agents.geopolitical_agent import _signal

class SanctionsAgent:
    name = "sanctions_agent"
    def evaluate(self, state=None):
        s = state or {}
        score = float(s.get("sanctions_score", 0) or 0)
        if score >= 55:
            return [_signal(self.name, "SANCTIONS_PRESSURE_SPIKE", min(.9, .5 + score / 220), "high" if score >= 70 else "medium", "bearish", "reduce_sanctions_sensitive_exposure", f"Sanctions pressure score {score:.1f}", ["XLE", "SMH", "QQQ", "BTC", "USDC"], ["Russia/Ukraine", "China", "Middle East"], s.get("data_quality", "degraded"), s.get("timestamp"))]
        return []
