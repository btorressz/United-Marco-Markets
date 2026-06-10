from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_consensus(signals: list[dict[str, Any]]) -> dict[str, Any]:
    bulls = [s for s in signals if s.get("direction") == "bullish"]
    bears = [s for s in signals if s.get("direction") == "bearish"]
    neutrals = [s for s in signals if s.get("direction") not in {"bullish", "bearish"}]
    weighted = sum((1 if s.get("direction") == "bullish" else -1 if s.get("direction") == "bearish" else 0) * float(s.get("confidence", .5) or .5) for s in signals)
    total_conf = sum(float(s.get("confidence", .5) or .5) for s in signals) or 1.0
    score = weighted / total_conf
    disagreement = 1.0 - abs(score) if signals else 0.0
    proposed = "reduce_risk" if score < -.25 else "add_risk_carefully" if score > .25 else "hold_monitor"
    return {"bullish_count": len(bulls), "bearish_count": len(bears), "neutral_count": len(neutrals), "risk_on_risk_off_score": round((score + 1) * 50, 2), "confidence_weighted_consensus": "bullish" if score > .25 else "bearish" if score < -.25 else "neutral", "disagreement_level": round(disagreement, 4), "proposed_action": proposed, "top_agreeing_agents": [s.get("agent") for s in sorted(signals, key=lambda x: float(x.get("confidence", 0)), reverse=True)[:5]], "conflicting_agents": list({s.get("agent") for s in bulls[:3] + bears[:3] if s.get("agent")}), "proposal_only": True, "ts": datetime.now(timezone.utc).isoformat()}
