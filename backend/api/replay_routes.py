import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from backend.core.event_bus import EventBus
from backend.compute.replay_engine import run_replay, get_latest_replay

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/replay", tags=["replay"])

_bus = EventBus()


@router.post("/run")
def run_replay_endpoint(body: dict = {}):
    try:
        events = _bus.get_recent(limit=body.get("limit", 200))
        result = run_replay(
            events=events,
            strategy_config=body.get("strategy_config"),
            start_ts=body.get("start_ts"),
            end_ts=body.get("end_ts"),
        )
        return result
    except Exception as exc:
        logger.error("Replay run failed: %s", exc, exc_info=True)
        return {"status": "error", "error": str(exc), "ts": datetime.now(timezone.utc).isoformat()}


@router.get("/latest")
def get_latest():
    result = get_latest_replay()
    if result:
        return result
    return {"status": "no_replay", "message": "No replay run yet", "ts": datetime.now(timezone.utc).isoformat()}

@router.post("/trade-simulation")
def trade_simulation(body: dict = {}):
    try:
        scenario = body.get("scenario", "tariff_shock")
        steps = int(body.get("steps", 12) or 12)
        capital = float(body.get("initial_capital", 100000.0) or 100000.0)
        timeline = []
        equity = capital
        peak = capital
        max_dd = 0.0
        per_strategy = {"macro_defensive": 0.0, "equity_tariff": 0.0}
        for i in range(max(2, min(steps, 60))):
            shock = min(1.0, 0.2 + i / max(steps, 1) * (0.55 if scenario == "tariff_shock" else 0.25))
            signal = {"agent": "replay_agent", "signal": "EQUITY_TARIFF_RISK_HIGH" if shock > 0.55 else "WATCH", "confidence": round(0.5 + shock * 0.35, 3), "severity": "high" if shock > 0.7 else "medium", "direction": "bearish", "proposed_action": "reduce_size" if shock > 0.55 else "hold"}
            alloc = {"cash": round(0.10 + shock * 0.25, 4), "risk_assets": round(0.90 - shock * 0.25, 4)}
            order = {"market": "SPY", "side": "sell" if shock > 0.55 else "hold", "size": round(shock * 10, 4), "status": "simulated_decision_only"}
            pnl = (-0.002 + (0.004 if order["side"] == "sell" else -0.001) * shock) * equity
            equity += pnl
            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / peak if peak else 0)
            per_strategy["macro_defensive"] += pnl * 0.6
            per_strategy["equity_tariff"] += pnl * 0.4
            timeline.append({"step": i + 1, "portfolio_value": round(equity, 2), "agent_signals": [signal], "proposed_actions": [signal["proposed_action"]], "allocation_changes": alloc, "simulated_orders": [order], "decision_log": "proposal-only replay; no real trade executed"})
        return {"status": "ok", "scenario": scenario, "simulated_timeline": timeline, "agent_signals": [x for t in timeline for x in t["agent_signals"]], "proposed_actions": [t["proposed_actions"] for t in timeline], "allocation_changes": [t["allocation_changes"] for t in timeline], "simulated_orders": [o for t in timeline for o in t["simulated_orders"]], "final_portfolio_value": round(equity, 2), "max_drawdown": round(max_dd, 6), "per_strategy_pnl": {k: round(v, 2) for k, v in per_strategy.items()}, "warnings": ["simulation only; no paper or live orders submitted"], "ts": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        logger.error("Trade simulation failed", exc_info=True)
        return {"status": "degraded", "simulated_timeline": [], "warnings": [str(exc)], "ts": datetime.now(timezone.utc).isoformat()}
