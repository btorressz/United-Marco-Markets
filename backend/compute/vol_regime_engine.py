import logging
import math
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

REGIMES = ["low_volatility", "normal_volatility", "high_volatility", "shock_regime", "liquidity_crunch"]


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def classify_regime(state: dict[str, Any] | None = None) -> dict[str, Any]:
    state = state or {}

    annualized_vol = _clamp(float(state.get("annualized_vol", 0.40)), 0.0, 5.0)
    shock_score = _clamp(float(state.get("shock_score", 0.0)), -3.0, 3.0)
    tariff_index = _clamp(float(state.get("tariff_index", 30.0)), 0.0, 100.0)
    stable_health = _clamp(float(state.get("stable_health", 1.0)), 0.0, 1.0)
    funding_skew = float(state.get("funding_skew", 0.0))
    divergence_score = _clamp(float(state.get("divergence_score", 0.0)), 0.0, 1.0)
    orderbook_depth = _clamp(float(state.get("orderbook_depth_score", 1.0)), 0.0, 1.0)
    exec_quality = _clamp(float(state.get("exec_quality", 0.8)), 0.0, 1.0)

    scores = {
        "low_volatility": 0.0,
        "normal_volatility": 0.0,
        "high_volatility": 0.0,
        "shock_regime": 0.0,
        "liquidity_crunch": 0.0,
    }

    if annualized_vol < 0.20:
        scores["low_volatility"] += 0.5
    elif annualized_vol < 0.50:
        scores["normal_volatility"] += 0.4
    elif annualized_vol < 0.90:
        scores["high_volatility"] += 0.4
    else:
        scores["shock_regime"] += 0.3
        scores["high_volatility"] += 0.2

    if abs(shock_score) > 1.5:
        scores["shock_regime"] += 0.35
    elif abs(shock_score) > 0.8:
        scores["high_volatility"] += 0.2
    elif abs(shock_score) < 0.3:
        scores["low_volatility"] += 0.15

    if tariff_index > 70:
        scores["shock_regime"] += 0.25
    elif tariff_index > 50:
        scores["high_volatility"] += 0.10

    if stable_health < 0.5:
        scores["liquidity_crunch"] += 0.4
        scores["shock_regime"] += 0.15
    elif stable_health < 0.75:
        scores["liquidity_crunch"] += 0.20

    if orderbook_depth < 0.3:
        scores["liquidity_crunch"] += 0.3
    elif orderbook_depth < 0.6:
        scores["liquidity_crunch"] += 0.10

    if exec_quality < 0.4:
        scores["liquidity_crunch"] += 0.2

    if divergence_score > 0.7:
        scores["shock_regime"] += 0.15
        scores["high_volatility"] += 0.10

    if abs(funding_skew) > 0.002:
        scores["high_volatility"] += 0.08

    regime = max(scores, key=lambda k: scores[k])
    confidence = _clamp(scores[regime] / max(sum(scores.values()), 0.01), 0.1, 0.95)
    if sum(scores.values()) < 0.01:
        regime = "normal_volatility"
        confidence = 0.3

    return {
        "regime": regime,
        "confidence": round(confidence, 3),
        "scores": {k: round(v, 4) for k, v in scores.items()},
        "inputs": {
            "annualized_vol": annualized_vol,
            "shock_score": shock_score,
            "tariff_index": tariff_index,
            "stable_health": stable_health,
            "orderbook_depth": orderbook_depth,
            "exec_quality": exec_quality,
        },
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def get_recommendations(regime: str, confidence: float = 0.5) -> dict[str, Any]:
    rec_map: dict[str, dict[str, Any]] = {
        "low_volatility": {
            "strategy_weight_changes": {
                "momentum": +0.10,
                "carry_arb": +0.05,
                "stable_rotation": -0.10,
                "defensive": -0.15,
            },
            "leverage_adjustment": "allow_up_to_3x",
            "slippage_tolerance": "tight",
            "hedge_aggressiveness": "low",
            "execution_style": "aggressive_limit_orders",
            "summary": "Low vol: maximize carry and momentum, tight slippage, normal sizing",
        },
        "normal_volatility": {
            "strategy_weight_changes": {
                "momentum": 0.0,
                "carry_arb": 0.0,
                "stable_rotation": 0.0,
                "defensive": 0.0,
            },
            "leverage_adjustment": "maintain_2x",
            "slippage_tolerance": "normal",
            "hedge_aggressiveness": "moderate",
            "execution_style": "limit_orders",
            "summary": "Normal vol: maintain standard sizing and strategy mix",
        },
        "high_volatility": {
            "strategy_weight_changes": {
                "momentum": -0.10,
                "carry_arb": -0.05,
                "stable_rotation": +0.10,
                "defensive": +0.10,
            },
            "leverage_adjustment": "reduce_to_1.5x",
            "slippage_tolerance": "wide",
            "hedge_aggressiveness": "high",
            "execution_style": "patient_limit_orders",
            "summary": "High vol: reduce size, widen slippage, increase hedging",
        },
        "shock_regime": {
            "strategy_weight_changes": {
                "momentum": -0.20,
                "carry_arb": -0.15,
                "stable_rotation": +0.20,
                "defensive": +0.25,
            },
            "leverage_adjustment": "reduce_to_1x",
            "slippage_tolerance": "very_wide",
            "hedge_aggressiveness": "maximum",
            "execution_style": "market_orders_only_for_exits",
            "summary": "Shock regime: reduce beta, increase stable allocation, hedge aggressively",
        },
        "liquidity_crunch": {
            "strategy_weight_changes": {
                "momentum": -0.25,
                "carry_arb": -0.20,
                "stable_rotation": +0.15,
                "defensive": +0.30,
            },
            "leverage_adjustment": "reduce_to_0.5x",
            "slippage_tolerance": "maximum_wide",
            "hedge_aggressiveness": "maximum",
            "execution_style": "pause_new_risk_exits_only",
            "summary": "Liquidity crunch: pause new risk, reduce order size, exits only",
        },
    }

    rec = rec_map.get(regime, rec_map["normal_volatility"])
    rec = dict(rec)
    rec["regime"] = regime
    rec["confidence"] = round(confidence, 3)
    rec["ts"] = datetime.now(timezone.utc).isoformat()
    return rec
