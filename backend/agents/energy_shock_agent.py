from __future__ import annotations
from backend.agents.geopolitical_agent import _signal

class EnergyShockAgent:
    name = "energy_shock_agent"
    def evaluate(self, state=None):
        s = state or {}
        score = float(s.get("energy_score", 0) or 0)
        signals = []
        if score >= 55:
            signals.append(_signal(self.name, "ENERGY_SHOCK_RISK", min(.9, .5 + score / 220), "high" if score >= 70 else "medium", "mixed", "hedge_energy_inflation_risk", f"Energy shock score {score:.1f}", ["USO", "XLE", "XOM", "CVX", "GLD"], ["Middle East", "Russia/Ukraine", "Hormuz"], s.get("data_quality", "degraded"), s.get("timestamp")))
        if (s.get("regional_breakdown") or {}).get("Strait of Hormuz", 0) >= 50:
            signals.append(_signal(self.name, "MIDDLE_EAST_OIL_RISK", .78, "high", "mixed", "review_oil_and_inflation_hedges", "Hormuz/Middle East stress can pressure oil and inflation", ["USO", "XLE", "XOM", "CVX"], ["Middle East", "Strait of Hormuz"], s.get("data_quality", "degraded"), s.get("timestamp")))
        return signals
