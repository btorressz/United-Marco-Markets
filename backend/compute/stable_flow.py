import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_history: list[dict] = []
MAX_HISTORY = 200


def compute_flow_momentum(
    stable_prices: dict | None = None,
    stable_volumes: dict | None = None,
    total_market_cap: float | None = None,
) -> dict:
    stable_prices = stable_prices or {}
    stable_volumes = stable_volumes or {}

    drivers: list[str] = []
    momentum = 0.0

    usdt_price = stable_prices.get("usdt", 1.0)
    usdc_price = stable_prices.get("usdc", 1.0)
    dai_price = stable_prices.get("dai", 1.0)

    peg_deviations = {
        "usdt": abs(usdt_price - 1.0),
        "usdc": abs(usdc_price - 1.0),
        "dai": abs(dai_price - 1.0),
    }
    avg_peg_dev = sum(peg_deviations.values()) / max(len(peg_deviations), 1)

    if avg_peg_dev > 0.005:
        momentum -= 0.3
        drivers.append(f"peg_stress: avg_deviation={avg_peg_dev:.4f}")
    elif avg_peg_dev > 0.002:
        momentum -= 0.1
        drivers.append(f"mild_peg_pressure: avg_deviation={avg_peg_dev:.4f}")
    else:
        drivers.append(f"peg_healthy: avg_deviation={avg_peg_dev:.4f}")

    usdt_vol = stable_volumes.get("usdt", 0)
    usdc_vol = stable_volumes.get("usdc", 0)
    dai_vol = stable_volumes.get("dai", 0)
    total_stable_vol = usdt_vol + usdc_vol + dai_vol

    if total_market_cap and total_market_cap > 0 and total_stable_vol > 0:
        dominance_ratio = total_stable_vol / total_market_cap
        if dominance_ratio > 0.05:
            momentum -= 0.3
            drivers.append(f"high_stable_dominance: ratio={dominance_ratio:.4f}")
        elif dominance_ratio > 0.02:
            momentum -= 0.1
            drivers.append(f"moderate_stable_dominance: ratio={dominance_ratio:.4f}")
        else:
            momentum += 0.2
            drivers.append(f"low_stable_dominance: ratio={dominance_ratio:.4f}")
    elif total_stable_vol > 0:
        drivers.append("market_cap_unavailable: using volume signals only")

    if total_stable_vol > 0:
        usdc_share = usdc_vol / total_stable_vol if total_stable_vol else 0
        if usdc_share > 0.5:
            momentum += 0.15
            drivers.append(f"usdc_inflow_dominant: share={usdc_share:.2f}")
        elif usdc_share < 0.2:
            momentum -= 0.1
            drivers.append(f"usdc_outflow_signal: share={usdc_share:.2f}")

    if len(_history) >= 2:
        prev = _history[-1]
        prev_momentum = prev.get("stable_flow_momentum", 0)
        delta = momentum - prev_momentum
        if abs(delta) > 0.3:
            momentum += delta * 0.2
            drivers.append(f"momentum_acceleration: delta={delta:.3f}")

    momentum = max(-1.0, min(1.0, momentum))

    if momentum > 0.15:
        risk_indicator = "risk_on"
    elif momentum < -0.15:
        risk_indicator = "risk_off"
    else:
        risk_indicator = "neutral"

    result = {
        "stable_flow_momentum": round(momentum, 4),
        "risk_on_off_indicator": risk_indicator,
        "drivers": drivers,
        "peg_deviations": {k: round(v, 6) for k, v in peg_deviations.items()},
        "total_stable_volume": total_stable_vol,
        "ts": datetime.now(timezone.utc).isoformat(),
    }

    _history.append(result)
    if len(_history) > MAX_HISTORY:
        _history[:] = _history[-MAX_HISTORY:]

    return result


def get_history(limit: int = 50) -> list[dict]:
    return list(reversed(_history[-limit:]))
