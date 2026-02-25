import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SPREAD_THRESH_HIGH = 50.0
SPREAD_THRESH_MED = 20.0
IMPACT_THRESH_HIGH = 100.0
IMPACT_THRESH_MED = 30.0
RPC_LATENCY_THRESH_HIGH = 2000.0
RPC_LATENCY_THRESH_MED = 500.0
OB_DEPTH_THRESH_LOW = 5000.0
OB_DEPTH_THRESH_MED = 50000.0
CONGESTION_RPC_THRESH = 1500.0
CONGESTION_SLOT_DELTA_THRESH = 10


def compute_quality(
    spread_bps: float = 0.0,
    price_impact_bps: float = 0.0,
    rpc_latency_ms: float = 0.0,
    ob_depth: float = 0.0,
) -> dict:
    try:
        spread_score = max(0.0, 100.0 - (spread_bps / SPREAD_THRESH_HIGH) * 100.0)
        impact_score = max(0.0, 100.0 - (price_impact_bps / IMPACT_THRESH_HIGH) * 100.0)
        latency_score = max(0.0, 100.0 - (rpc_latency_ms / RPC_LATENCY_THRESH_HIGH) * 100.0)

        if ob_depth >= OB_DEPTH_THRESH_MED:
            depth_score = 100.0
        elif ob_depth >= OB_DEPTH_THRESH_LOW:
            depth_score = 50.0 + 50.0 * ((ob_depth - OB_DEPTH_THRESH_LOW) / (OB_DEPTH_THRESH_MED - OB_DEPTH_THRESH_LOW))
        else:
            depth_score = max(0.0, 50.0 * (ob_depth / OB_DEPTH_THRESH_LOW))

        execution_quality_score = round(
            0.30 * spread_score + 0.25 * impact_score + 0.25 * latency_score + 0.20 * depth_score,
            2,
        )
        execution_quality_score = max(0.0, min(100.0, execution_quality_score))

        if spread_bps >= SPREAD_THRESH_HIGH or price_impact_bps >= IMPACT_THRESH_HIGH:
            slippage_risk = "high"
        elif spread_bps >= SPREAD_THRESH_MED or price_impact_bps >= IMPACT_THRESH_MED:
            slippage_risk = "medium"
        else:
            slippage_risk = "low"

        congestion_warning = rpc_latency_ms >= CONGESTION_RPC_THRESH

        return {
            "execution_quality_score": execution_quality_score,
            "congestion_warning": congestion_warning,
            "slippage_risk": slippage_risk,
            "components": {
                "spread_score": round(spread_score, 2),
                "impact_score": round(impact_score, 2),
                "latency_score": round(latency_score, 2),
                "depth_score": round(depth_score, 2),
            },
            "inputs": {
                "spread_bps": spread_bps,
                "price_impact_bps": price_impact_bps,
                "rpc_latency_ms": rpc_latency_ms,
                "ob_depth": ob_depth,
            },
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    except Exception:
        logger.warning("compute_quality failed, returning defaults", exc_info=True)
        return {
            "execution_quality_score": 50.0,
            "congestion_warning": False,
            "slippage_risk": "low",
            "components": {},
            "inputs": {
                "spread_bps": spread_bps,
                "price_impact_bps": price_impact_bps,
                "rpc_latency_ms": rpc_latency_ms,
                "ob_depth": ob_depth,
            },
            "ts": datetime.now(timezone.utc).isoformat(),
        }


def assess_congestion(
    rpc_latency_ms: float = 0.0,
    slot_delta: int = 0,
) -> dict:
    try:
        is_congested = (
            rpc_latency_ms >= CONGESTION_RPC_THRESH
            or slot_delta >= CONGESTION_SLOT_DELTA_THRESH
        )

        if rpc_latency_ms >= CONGESTION_RPC_THRESH and slot_delta >= CONGESTION_SLOT_DELTA_THRESH:
            severity = "high"
        elif rpc_latency_ms >= CONGESTION_RPC_THRESH or slot_delta >= CONGESTION_SLOT_DELTA_THRESH:
            severity = "medium"
        else:
            severity = "low"

        reasons = []
        if rpc_latency_ms >= CONGESTION_RPC_THRESH:
            reasons.append(f"RPC latency {rpc_latency_ms:.0f}ms exceeds {CONGESTION_RPC_THRESH:.0f}ms threshold")
        if slot_delta >= CONGESTION_SLOT_DELTA_THRESH:
            reasons.append(f"Slot delta {slot_delta} exceeds {CONGESTION_SLOT_DELTA_THRESH} threshold")

        recommended_action = "proceed"
        if severity == "high":
            recommended_action = "delay_execution"
        elif severity == "medium":
            recommended_action = "reduce_size"

        return {
            "congested": is_congested,
            "severity": severity,
            "reasons": reasons,
            "recommended_action": recommended_action,
            "inputs": {
                "rpc_latency_ms": rpc_latency_ms,
                "slot_delta": slot_delta,
            },
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    except Exception:
        logger.warning("assess_congestion failed, returning defaults", exc_info=True)
        return {
            "congested": False,
            "severity": "low",
            "reasons": [],
            "recommended_action": "proceed",
            "inputs": {
                "rpc_latency_ms": rpc_latency_ms,
                "slot_delta": slot_delta,
            },
            "ts": datetime.now(timezone.utc).isoformat(),
        }


def estimate_jupiter_route(
    input_mint: str = "SOL",
    output_mint: str = "USDC",
    amount_usd: float = 1000.0,
    cached_depth: float = 0.0,
    cached_impact_bps: float = 0.0,
) -> dict:
    try:
        if cached_depth > 0:
            estimated_impact = cached_impact_bps * (amount_usd / max(cached_depth, 1.0))
        else:
            estimated_impact = 10.0

        if amount_usd <= 1000:
            estimated_hops = 1
        elif amount_usd <= 10000:
            estimated_hops = 2
        else:
            estimated_hops = 3

        if estimated_impact > 100:
            risk_level = "high"
        elif estimated_impact > 30:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "input_mint": input_mint,
            "output_mint": output_mint,
            "amount_usd": amount_usd,
            "estimated_price_impact_bps": round(estimated_impact, 2),
            "estimated_hops": estimated_hops,
            "risk_level": risk_level,
            "depth_available": cached_depth,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    except Exception:
        logger.warning("estimate_jupiter_route failed, returning defaults", exc_info=True)
        return {
            "input_mint": input_mint,
            "output_mint": output_mint,
            "amount_usd": amount_usd,
            "estimated_price_impact_bps": 10.0,
            "estimated_hops": 1,
            "risk_level": "low",
            "depth_available": 0.0,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
