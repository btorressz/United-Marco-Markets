from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def scenario_templates() -> dict[str, Any]:
    return {"templates": [
        {"id": "tariff_shock", "name": "Tariff Shock", "inputs": {"tariff_index_change": 20, "gdelt_shock_change": 1.0, "equity_drawdown": -0.04, "crypto_drawdown": -0.03, "stablecoin_depeg": 10, "funding_flip": True, "liquidity_depth_drop": 0.25, "volatility_spike": 0.35}},
        {"id": "stablecoin_stress", "name": "Stablecoin Stress", "inputs": {"tariff_index_change": 5, "gdelt_shock_change": 0.4, "equity_drawdown": -0.015, "crypto_drawdown": -0.06, "stablecoin_depeg": 45, "funding_flip": True, "liquidity_depth_drop": 0.45, "volatility_spike": 0.55}},
        {"id": "soft_landing", "name": "Soft Landing", "inputs": {"tariff_index_change": -5, "gdelt_shock_change": -0.2, "equity_drawdown": 0.01, "crypto_drawdown": 0.015, "stablecoin_depeg": 0, "funding_flip": False, "liquidity_depth_drop": 0.0, "volatility_spike": -0.1}},
    ], "ts": datetime.now(timezone.utc).isoformat()}


def run_scenario(inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    i = inputs or {}
    tariff = float(i.get("tariff_index_change", 0) or 0)
    gdelt = float(i.get("gdelt_shock_change", 0) or 0)
    eq = float(i.get("equity_drawdown", 0) or 0)
    crypto = float(i.get("crypto_drawdown", 0) or 0)
    depeg = float(i.get("stablecoin_depeg", 0) or 0)
    liq = float(i.get("liquidity_depth_drop", 0) or 0)
    vol = float(i.get("volatility_spike", 0) or 0)
    funding_flip = bool(i.get("funding_flip", False))
    risk = min(1.0, max(0.0, tariff / 30 + gdelt / 4 + abs(min(eq, 0)) * 5 + abs(min(crypto, 0)) * 3 + depeg / 100 + liq + max(vol, 0)))
    pnl = 100000 * (eq * .55 + crypto * .25 - depeg / 10000 - liq * .015)
    signals = [{"agent": "scenario_engine", "signal": "SCENARIO_RISK_OFF" if risk > .45 else "SCENARIO_NEUTRAL", "confidence": round(.55 + risk * .35, 3), "severity": "high" if risk > .7 else "medium" if risk > .35 else "low", "direction": "bearish" if risk > .45 else "neutral", "proposed_action": "reduce_risk_and_preview_hedges" if risk > .45 else "monitor", "reason": "Hypothetical stress inputs mapped to proposal-only risk response", "ts": datetime.now(timezone.utc).isoformat()}]
    return {"portfolio_pnl_impact": round(pnl, 2), "agent_signals": signals, "allocation_changes": {"cash": round(.10 + risk * .35, 4), "stables": round(.15 + risk * .20, 4), "risk_assets": round(max(.0, .75 - risk * .55), 4)}, "hedge_recommendations": ["reduce high tariff-beta names", "hedge QQQ/SMH/SPY" if risk > .45 else "no hedge required", "rotate to cash/stables" if depeg < 25 and risk > .45 else "monitor stablecoin venue risk"], "conditional_orders_triggered": ["stop_loss", "trailing_stop"] if risk > .65 else [], "execution_warnings": ["liquidity depth degraded" if liq > .25 else "normal liquidity", "funding flip risk" if funding_flip else "funding stable"], "degraded": False, "ts": datetime.now(timezone.utc).isoformat()}
