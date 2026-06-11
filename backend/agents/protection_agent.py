from __future__ import annotations
from backend.agents.geopolitical_agent import _signal

class ProtectionAgent:
    name = "protection_agent"
    def evaluate(self, state=None):
        s = state or {}
        mode = s.get("protection_mode", "NORMAL")
        if mode in {"DEFENSIVE", "CRISIS"}:
            sig = "PORTFOLIO_PROTECTION_CRISIS" if mode == "CRISIS" else "PORTFOLIO_PROTECTION_DEFENSIVE"
            return [_signal(self.name, sig, .82 if mode == "CRISIS" else .72, mode.lower(), "bearish", "activate_protection_preview", f"Protection protocol mode is {mode}; proposal-only actions recommended", ["SPY", "QQQ", "SMH", "XRT", "BTC", "SOL"], ["Global"], s.get("data_quality", "degraded"), s.get("timestamp"))]
        return []
