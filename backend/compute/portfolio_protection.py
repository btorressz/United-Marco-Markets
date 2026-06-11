from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _mode(score: float) -> str:
    return "CRISIS" if score >= 85 else "DEFENSIVE" if score >= 65 else "WATCH" if score >= 35 else "NORMAL"


def protection_protocol(inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    i = inputs or {}
    geo = i.get("geopolitical_index") or {}
    score = float(geo.get("overall_score", i.get("geopolitical_score", 45.0)) or 45.0)
    stable = float(i.get("stablecoin_stress", 5.0) or 5.0)
    exec_quality = float(i.get("execution_quality", 0.8) or 0.8)
    dq = i.get("data_quality", geo.get("data_quality", "degraded"))
    mode = _mode(score + min(stable, 30) * .25 + (1 - exec_quality) * 12)
    defensive = mode in {"DEFENSIVE", "CRISIS"}
    return {
        "protection_mode": mode, "proposal_only": True, "auto_trade": False,
        "recommended_actions": ["pause new longs" if defensive else "monitor", "reduce high geopolitical-beta names" if defensive else "maintain sizing discipline", "wait for data freshness recovery" if dq == "degraded" else "continue data-quality checks"],
        "reduce_leverage_suggestion": "reduce 25-50%" if mode == "CRISIS" else "reduce 10-25%" if mode == "DEFENSIVE" else "no change",
        "raise_cash_or_stables_suggestion": "raise cash/stables allocation" if defensive else "normal cash buffer",
        "hedge_suggestions": ["hedge QQQ/SPY/SMH/XRT exposure", "consider ITA/GLD/XLE protective baskets" if score >= 55 else "hedges optional"],
        "stop_loss_or_bracket_order_suggestions": ["tighten stop losses", "activate bracket order suggestions"] if defensive else ["standard stops"],
        "execution_mode_suggestion": "paper/conservative only", "slippage_caution": "widen slippage caution" if defensive else "normal slippage caution",
        "position_size_adjustments": {"high_geo_beta": -0.35 if mode == "CRISIS" else -0.20 if mode == "DEFENSIVE" else -0.05, "cash": 0.25 if defensive else 0.05},
        "invalidation_conditions": ["geopolitical index falls below WATCH", "GDELT/WITS data freshness recovers", "agent consensus turns neutral/risk-on", "stablecoin stress normalizes"],
        "confidence": 0.55 if dq == "degraded" else 0.76, "reasoning": ["Portfolio protection protocol is proposal-only", "Mode maps geopolitical score, stablecoin stress, execution quality, and data quality to conservative actions"], "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def scenario_protection(scenario: dict[str, Any], index: dict[str, Any] | None = None) -> dict[str, Any]:
    score = max(float((index or {}).get("overall_score", 0) or 0), float(scenario.get("severity", 50) or 50))
    return protection_protocol({"geopolitical_score": score, "stablecoin_stress": scenario.get("stablecoin_stress", 10), "data_quality": scenario.get("data_quality", "degraded")})
