import logging
import math
import time
from datetime import datetime, timezone
from typing import Any

from backend.compute.rules_engine import RulesEngine
from backend.compute.monte_carlo import MonteCarloEngine

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_A = {
    "name": "Config A (Default)",
    "tariff_shock_threshold": 60.0,
    "divergence_threshold_bps": 30.0,
    "funding_flip_threshold": 0.0,
    "vol_scale_factor": 1.0,
    "stable_rotation_trigger": 0.5,
}

DEFAULT_CONFIG_B = {
    "name": "Config B (Aggressive)",
    "tariff_shock_threshold": 40.0,
    "divergence_threshold_bps": 20.0,
    "funding_flip_threshold": -0.01,
    "vol_scale_factor": 1.5,
    "stable_rotation_trigger": 0.3,
}

_latest_result: dict[str, Any] | None = None
_history: list[dict[str, Any]] = []
MAX_HISTORY = 50


def _simulate_strategy(config: dict, market_state: dict) -> dict:
    engine = RulesEngine()
    actions = engine.evaluate(market_state)

    decisions = []
    pnl = 0.0
    trades = 0

    for action in actions:
        triggered = action.get("triggered", False)
        if triggered:
            trades += 1
            size = action.get("size", 0.1) * config.get("vol_scale_factor", 1.0)
            simulated_pnl = size * market_state.get("price_change_pct", 0) / 100.0
            pnl += simulated_pnl
            decisions.append({
                "rule": action.get("rule", "unknown"),
                "action": action.get("action", "none"),
                "size": round(size, 4),
                "simulated_pnl": round(simulated_pnl, 4),
            })

    mc_result = {}
    try:
        mc_engine = MonteCarloEngine()
        mc_result = mc_engine.run(
            current_price=market_state.get("current_price", 100.0),
            horizon_hours=24,
            n_paths=1000,
            volatility=market_state.get("volatility", 0.03),
            position_size=1.0,
        )
    except Exception:
        logger.debug("MC simulation failed in sandbox", exc_info=True)

    var_95 = mc_result.get("var_95", 0)
    cvar_95 = mc_result.get("cvar_95", 0)

    max_drawdown = abs(min(pnl, 0)) if pnl < 0 else 0
    hit_rate = (sum(1 for d in decisions if d["simulated_pnl"] > 0) / max(len(decisions), 1))
    avg_slippage_est = market_state.get("spread_bps", 5.0) * 0.5

    return {
        "config_name": config.get("name", "Unknown"),
        "config": config,
        "decisions": decisions,
        "trade_count": trades,
        "total_pnl": round(pnl, 6),
        "max_drawdown": round(max_drawdown, 6),
        "hit_rate": round(hit_rate, 4),
        "var_95": round(var_95, 4) if var_95 else 0,
        "cvar_95": round(cvar_95, 4) if cvar_95 else 0,
        "turnover": trades,
        "avg_slippage_est_bps": round(avg_slippage_est, 2),
    }


def run_sandbox(
    config_a: dict | None = None,
    config_b: dict | None = None,
    market_state: dict | None = None,
) -> dict[str, Any]:
    global _latest_result

    config_a = {**DEFAULT_CONFIG_A, **(config_a or {})}
    config_b = {**DEFAULT_CONFIG_B, **(config_b or {})}
    market_state = market_state or {}

    if "current_price" not in market_state:
        market_state["current_price"] = 100.0
    if "price_change_pct" not in market_state:
        market_state["price_change_pct"] = 0.0

    result_a = _simulate_strategy(config_a, market_state)
    result_b = _simulate_strategy(config_b, market_state)

    winner = "A" if result_a["total_pnl"] >= result_b["total_pnl"] else "B"
    pnl_diff = abs(result_a["total_pnl"] - result_b["total_pnl"])

    highlights = []
    if result_a["hit_rate"] > result_b["hit_rate"]:
        highlights.append(f"Config A has higher hit rate ({result_a['hit_rate']:.0%} vs {result_b['hit_rate']:.0%})")
    elif result_b["hit_rate"] > result_a["hit_rate"]:
        highlights.append(f"Config B has higher hit rate ({result_b['hit_rate']:.0%} vs {result_a['hit_rate']:.0%})")
    if result_a["max_drawdown"] < result_b["max_drawdown"]:
        highlights.append("Config A has lower drawdown")
    elif result_b["max_drawdown"] < result_a["max_drawdown"]:
        highlights.append("Config B has lower drawdown")
    if result_a["trade_count"] != result_b["trade_count"]:
        highlights.append(f"Trade count: A={result_a['trade_count']} vs B={result_b['trade_count']}")

    result = {
        "strategy_a": result_a,
        "strategy_b": result_b,
        "winner": winner,
        "pnl_difference": round(pnl_diff, 6),
        "highlights": highlights,
        "market_state_used": {
            "current_price": market_state.get("current_price"),
            "price_change_pct": market_state.get("price_change_pct"),
        },
        "ts": datetime.now(timezone.utc).isoformat(),
    }

    _latest_result = result
    _history.append(result)
    if len(_history) > MAX_HISTORY:
        _history.pop(0)

    return result


def get_latest() -> dict[str, Any] | None:
    return _latest_result


def get_history() -> list[dict[str, Any]]:
    return list(_history)
