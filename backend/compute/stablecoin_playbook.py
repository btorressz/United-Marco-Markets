import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

DEPEG_WARN_BPS = 30.0
DEPEG_ALERT_BPS = 50.0
STRESS_THRESHOLD = 0.5
PEG_BREAK_PROB_THRESHOLD = 0.3


def evaluate_playbook(
    depeg_bps: float = 0,
    stress_score: float = 0,
    peg_break_prob: float = 0,
    margin_usage: float = 0,
    vol_regime: str = "normal",
    stable_allocation_pct: float = 0.25,
    current_leverage: float = 1.0,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()

    triggered = False
    urgency = "none"
    actions = []
    reasoning = []
    confidence = 0.0

    if depeg_bps > DEPEG_ALERT_BPS:
        triggered = True
        urgency = "high"
        confidence += 0.3
        actions.append({
            "action": "reduce_leverage",
            "detail": f"Reduce leverage from {current_leverage:.1f}x — depeg {depeg_bps:.0f}bps is critical",
            "priority": 1,
        })
        actions.append({
            "action": "diversify_stables",
            "detail": "Rotate away from depegging stable to USDC/DAI",
            "priority": 2,
        })
        reasoning.append(f"Depeg {depeg_bps:.0f}bps exceeds alert threshold ({DEPEG_ALERT_BPS:.0f}bps)")

    elif depeg_bps > DEPEG_WARN_BPS:
        triggered = True
        urgency = "medium"
        confidence += 0.2
        actions.append({
            "action": "monitor_closely",
            "detail": f"Depeg {depeg_bps:.0f}bps approaching alert level — prepare rotation plan",
            "priority": 3,
        })
        reasoning.append(f"Depeg {depeg_bps:.0f}bps exceeds warning threshold ({DEPEG_WARN_BPS:.0f}bps)")

    if stress_score > STRESS_THRESHOLD:
        triggered = True
        if urgency != "high":
            urgency = "high" if stress_score > 0.7 else "medium"
        confidence += 0.2
        actions.append({
            "action": "hedge_risk_assets",
            "detail": f"Stress score {stress_score:.2f} elevated — hedge directional exposure via HL/Drift shorts",
            "priority": 2,
        })
        reasoning.append(f"Stress score {stress_score:.2f} exceeds threshold ({STRESS_THRESHOLD})")

    if peg_break_prob > PEG_BREAK_PROB_THRESHOLD:
        triggered = True
        urgency = "high"
        confidence += 0.25
        actions.append({
            "action": "defensive_rotation",
            "detail": f"Peg break probability {peg_break_prob:.0%} — emergency rotation to safer stables",
            "priority": 1,
        })
        actions.append({
            "action": "risk_throttle",
            "detail": "Activate risk throttle — block new positions until peg stabilizes",
            "priority": 1,
        })
        reasoning.append(f"Peg break probability {peg_break_prob:.0%} exceeds threshold ({PEG_BREAK_PROB_THRESHOLD:.0%})")

    if triggered and margin_usage > 0.5:
        actions.append({
            "action": "reduce_leverage",
            "detail": f"Margin usage {margin_usage:.0%} elevated during stablecoin stress — deleverage",
            "priority": 1,
        })
        confidence += 0.1
        reasoning.append(f"High margin usage ({margin_usage:.0%}) compounds stablecoin risk")

    if triggered and vol_regime in ("high", "extreme"):
        actions.append({
            "action": "reduce_position_sizes",
            "detail": f"Vol regime '{vol_regime}' + stablecoin stress — reduce all position sizes by 30-50%",
            "priority": 2,
        })
        confidence += 0.1
        reasoning.append(f"Vol regime '{vol_regime}' amplifies stablecoin risk")

    actions.sort(key=lambda a: a.get("priority", 99))

    confidence = min(round(0.50 + confidence, 2), 0.95) if triggered else 0.0

    return {
        "triggered": triggered,
        "urgency": urgency,
        "actions": actions,
        "reasoning": reasoning,
        "confidence": confidence,
        "inputs": {
            "depeg_bps": depeg_bps,
            "stress_score": stress_score,
            "peg_break_prob": peg_break_prob,
            "margin_usage": margin_usage,
            "vol_regime": vol_regime,
            "stable_allocation_pct": stable_allocation_pct,
            "current_leverage": current_leverage,
        },
        "ts": now,
    }
