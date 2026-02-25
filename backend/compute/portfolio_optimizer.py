import logging
import math
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

ASSET_CLASSES = ["hl_perps", "drift_perps", "spot_jupiter", "stablecoins"]

DEFAULT_WEIGHTS = {
    "hl_perps": 0.25,
    "drift_perps": 0.25,
    "spot_jupiter": 0.25,
    "stablecoins": 0.25,
}

HARD_CAPS = {
    "hl_perps": 0.50,
    "drift_perps": 0.50,
    "spot_jupiter": 0.50,
    "stablecoins": 0.80,
}

HARD_FLOORS = {
    "hl_perps": 0.0,
    "drift_perps": 0.0,
    "spot_jupiter": 0.0,
    "stablecoins": 0.05,
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    return {k: v / total for k, v in weights.items()}


def _apply_caps(weights: dict[str, float]) -> dict[str, float]:
    capped = {}
    for k in ASSET_CLASSES:
        capped[k] = _clamp(weights.get(k, 0.0), HARD_FLOORS[k], HARD_CAPS[k])
    return _normalize(capped)


def risk_parity(
    vol_hl: float = 0.30,
    vol_drift: float = 0.30,
    vol_spot: float = 0.25,
    vol_stable: float = 0.02,
) -> dict[str, float]:
    vols = {
        "hl_perps": max(vol_hl, 0.01),
        "drift_perps": max(vol_drift, 0.01),
        "spot_jupiter": max(vol_spot, 0.01),
        "stablecoins": max(vol_stable, 0.001),
    }
    inv_vols = {k: 1.0 / v for k, v in vols.items()}
    return _normalize(inv_vols)


def mean_variance(
    expected_returns: dict[str, float],
    vols: dict[str, float],
    risk_aversion: float = 2.0,
) -> dict[str, float]:
    scores = {}
    for k in ASSET_CLASSES:
        mu = expected_returns.get(k, 0.0)
        sigma = max(vols.get(k, 0.01), 0.01)
        scores[k] = max(mu - 0.5 * risk_aversion * sigma * sigma, 0.001)
    return _normalize(scores)


def scaled_kelly(
    edge: dict[str, float],
    odds: dict[str, float],
    kelly_fraction: float = 0.25,
) -> dict[str, float]:
    raw = {}
    for k in ASSET_CLASSES:
        e = edge.get(k, 0.0)
        o = max(odds.get(k, 1.0), 0.01)
        p = _clamp(0.5 + e / (2.0 * o), 0.0, 1.0)
        q = 1.0 - p
        if o * p - q > 0:
            kelly = (o * p - q) / o
        else:
            kelly = 0.0
        raw[k] = max(kelly * kelly_fraction, 0.0)
    total = sum(raw.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    return _normalize(raw)


def optimize(inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    inputs = inputs or {}

    risk_limit = _clamp(inputs.get("risk_limit", 0.5), 0.0, 1.0)
    predictor_prob = _clamp(inputs.get("predictor_prob", 0.5), 0.0, 1.0)
    carry_score = inputs.get("carry_score", 0.0)
    macro_regime = inputs.get("macro_regime", "neutral")
    stable_rotation_pref = _clamp(inputs.get("stable_rotation_pref", 0.0), -1.0, 1.0)
    method = inputs.get("method", "risk_parity")

    reasoning = []

    if method == "mean_variance":
        er = {
            "hl_perps": carry_score * 0.5 + predictor_prob * 0.1,
            "drift_perps": carry_score * 0.4 + predictor_prob * 0.1,
            "spot_jupiter": predictor_prob * 0.15,
            "stablecoins": 0.04,
        }
        vols = {
            "hl_perps": 0.35,
            "drift_perps": 0.35,
            "spot_jupiter": 0.28,
            "stablecoins": 0.02,
        }
        weights = mean_variance(er, vols)
        reasoning.append("mean_variance: weights derived from expected returns vs vol")
    elif method == "kelly":
        edge = {
            "hl_perps": carry_score * 0.3,
            "drift_perps": carry_score * 0.25,
            "spot_jupiter": predictor_prob * 0.2 - 0.05,
            "stablecoins": 0.02,
        }
        odds = {k: 1.0 for k in ASSET_CLASSES}
        weights = scaled_kelly(edge, odds)
        reasoning.append("scaled_kelly: fractional Kelly sizing with 0.25x scaling")
    else:
        weights = risk_parity()
        reasoning.append("risk_parity: inverse-vol allocation across venues")

    if macro_regime in ("risk_off", "crisis"):
        shift = 0.15
        weights["stablecoins"] = weights.get("stablecoins", 0.25) + shift
        weights["hl_perps"] = weights.get("hl_perps", 0.25) - shift * 0.4
        weights["drift_perps"] = weights.get("drift_perps", 0.25) - shift * 0.3
        weights["spot_jupiter"] = weights.get("spot_jupiter", 0.25) - shift * 0.3
        reasoning.append(f"macro_regime={macro_regime}: shifted toward stablecoins")
    elif macro_regime == "risk_on":
        shift = 0.10
        weights["stablecoins"] = weights.get("stablecoins", 0.25) - shift
        weights["hl_perps"] = weights.get("hl_perps", 0.25) + shift * 0.4
        weights["drift_perps"] = weights.get("drift_perps", 0.25) + shift * 0.3
        weights["spot_jupiter"] = weights.get("spot_jupiter", 0.25) + shift * 0.3
        reasoning.append("macro_regime=risk_on: shifted toward risk assets")

    if stable_rotation_pref > 0.3:
        bonus = stable_rotation_pref * 0.10
        weights["stablecoins"] = weights.get("stablecoins", 0.25) + bonus
        reasoning.append(f"stable_rotation_pref={stable_rotation_pref:.2f}: boosted stablecoins")
    elif stable_rotation_pref < -0.3:
        penalty = abs(stable_rotation_pref) * 0.08
        weights["stablecoins"] = weights.get("stablecoins", 0.25) - penalty
        reasoning.append(f"stable_rotation_pref={stable_rotation_pref:.2f}: reduced stablecoins")

    if risk_limit < 0.3:
        factor = risk_limit / 0.3
        for k in ["hl_perps", "drift_perps", "spot_jupiter"]:
            weights[k] = weights.get(k, 0.25) * factor
        weights["stablecoins"] = weights.get("stablecoins", 0.25) + (1.0 - factor) * 0.3
        reasoning.append(f"risk_limit={risk_limit:.2f}: scaled down risky allocations")

    for k in ASSET_CLASSES:
        weights[k] = max(weights.get(k, 0.0), 0.0)

    weights = _apply_caps(weights)

    total = sum(weights[k] for k in ASSET_CLASSES)
    if abs(total - 1.0) > 1e-9:
        weights = _normalize(weights)

    reasoning.append("proposal only — no auto-trade")

    return {
        "allocation": {k: round(weights[k], 6) for k in ASSET_CLASSES},
        "method": method,
        "reasoning": reasoning,
        "inputs_echo": {
            "risk_limit": risk_limit,
            "predictor_prob": predictor_prob,
            "carry_score": carry_score,
            "macro_regime": macro_regime,
            "stable_rotation_pref": stable_rotation_pref,
        },
        "ts": datetime.now(timezone.utc).isoformat(),
    }
