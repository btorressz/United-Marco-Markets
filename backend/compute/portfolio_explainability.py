from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def explain_portfolio(allocation: dict[str, Any] | None = None, agents: list[dict[str, Any]] | None = None, data_quality: dict[str, Any] | None = None) -> dict[str, Any]:
    allocation = allocation or {}
    agents = agents or []
    bearish = [a for a in agents if a.get("direction") == "bearish"]
    bullish = [a for a in agents if a.get("direction") == "bullish"]
    confidence = allocation.get("confidence", .55)
    stale = [s.get("name") for s in (data_quality or {}).get("sources", []) if s.get("degraded_mode")]
    return {"drivers": allocation.get("reasoning", ["allocator state unavailable; using safe defaults"]), "agent_agreement": {"bullish": len(bullish), "bearish": len(bearish), "neutral": max(0, len(agents) - len(bullish) - len(bearish))}, "data_freshness": {"degraded_sources": stale, "status": "degraded" if stale else "ok"}, "confidence": confidence, "invalidation_conditions": ["WITS/GDELT shock reverses", "price integrity warning", "stablecoin health degrades", "volatility regime normalizes"], "expected_upside": round(.03 * float(confidence), 4), "expected_downside": round(-.05 * (1 - float(confidence) + len(bearish) * .05), 4), "proposal_only": True, "ts": datetime.now(timezone.utc).isoformat()}


def explain_recommendation(rec_id: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = context or {}
    return {"id": rec_id, "drivers": ctx.get("drivers", ["risk score", "agent consensus", "data quality"]), "confidence": float(ctx.get("confidence", .6) or .6), "why_now": "Recommendation is based on current deterministic heuristics and latest available snapshots", "what_would_change_it": ["fresh contradictory agent signals", "lower tariff/GDELT shock", "improved liquidity and volatility"], "proposal_only": True, "ts": datetime.now(timezone.utc).isoformat()}
