import logging
from datetime import datetime, timezone
from fastapi import APIRouter

from backend.core.state_store import StateStore
from backend.agents.risk_agent import RiskAgent
from backend.agents.macro_agent import MacroAgent
from backend.agents.execution_agent import ExecutionAgent
from backend.agents.liquidity_agent import LiquidityAgent
from backend.agents.hyperliquid_agent import HyperliquidAgent
from backend.agents.jupiter_agent import JupiterAgent
from backend.agents.hedging_agent import HedgingAgent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents", tags=["agents"])

_store = StateStore()
_risk_agent = RiskAgent()
_macro_agent = MacroAgent()
_exec_agent = ExecutionAgent()
_liq_agent = LiquidityAgent()
_hl_agent = HyperliquidAgent()
_jup_agent = JupiterAgent()
_hedge_agent = HedgingAgent()


def _build_agent_state() -> dict:
    state = {}
    now = datetime.now(timezone.utc).isoformat()

    idx = _store.get_snapshot("index:latest")
    if idx:
        state["tariff_index"] = idx.get("tariff_index", 0)
        state["tariff_momentum"] = idx.get("rate_of_change", 0)
        state["shock_score"] = idx.get("shock_score", 0)
        state["data_ts"] = idx.get("ts", now)
    else:
        state["data_ts"] = now

    regime = _store.get_snapshot("regime:latest")
    if regime:
        state["vol_regime"] = regime.get("vol_regime", "normal")
        state["funding_regime"] = regime.get("funding_regime", "neutral")

    risk = _store.get_snapshot("risk:status")
    if risk:
        state["margin_usage"] = risk.get("margin_usage", 0)

    stable = _store.get_snapshot("stablecoin:health")
    if stable:
        state["stablecoin_health"] = stable

    micro = _store.get_snapshot("microstructure:latest")
    if micro:
        state["orderbook_imbalance"] = micro.get("imbalance", 0)
        state["spread_bps"] = micro.get("spread_bps", 0) if "spread_bps" in micro else 0

    integrity = _store.get_snapshot("price:integrity")
    if integrity:
        state["price_integrity"] = integrity.get("status", "OK")

    state["positions"] = []
    state["current_price"] = 0

    price_snap = _store.get_snapshot("price:pyth:SOL_USD")
    if not price_snap:
        price_snap = _store.get_snapshot("price:sol:pyth")
    if price_snap:
        state["current_price"] = price_snap.get("price", 0)

    predict = _store.get_snapshot("prediction:latest")
    if predict:
        state["predictor_prob"] = predict.get("probability_up", 0.5)

    carry = _store.get_snapshot("carry:latest")
    if carry:
        scores = carry.get("scores", [])
        if scores:
            state["carry_score"] = scores[0].get("annualized_carry", 0)

    return state


@router.get("/signals")
def get_agent_signals():
    state = _build_agent_state()
    signals = []

    try:
        signals.extend(_risk_agent.evaluate(state))
    except Exception:
        logger.debug("Risk agent error", exc_info=True)

    try:
        signals.extend(_macro_agent.evaluate(state))
    except Exception:
        logger.debug("Macro agent error", exc_info=True)

    try:
        signals.extend(_exec_agent.evaluate(state))
    except Exception:
        logger.debug("Execution agent error", exc_info=True)

    try:
        signals.extend(_liq_agent.evaluate(state))
    except Exception:
        logger.debug("Liquidity agent error", exc_info=True)

    try:
        signals.extend(_hl_agent.evaluate(state))
    except Exception:
        logger.debug("Hyperliquid agent error", exc_info=True)

    try:
        signals.extend(_jup_agent.evaluate(state))
    except Exception:
        logger.debug("Jupiter agent error", exc_info=True)

    try:
        signals.extend(_hedge_agent.evaluate(state))
    except Exception:
        logger.debug("Hedging agent error", exc_info=True)

    _store.set_snapshot("agents:signals", {"signals": signals, "ts": datetime.now(timezone.utc).isoformat()}, ttl=30)
    return {"signals": signals, "agent_count": 7, "ts": datetime.now(timezone.utc).isoformat()}


@router.get("/status")
def get_agent_status():
    cached = _store.get_snapshot("agents:signals")
    signal_count = 0
    if cached and "signals" in cached:
        signal_count = len(cached["signals"])

    return {
        "agents": [
            {"name": "risk_agent", "status": "active", "description": "Monitors leverage, margin, drawdown limits and throttle triggers"},
            {"name": "macro_agent", "status": "active", "description": "Evaluates tariff index, shock scores and macro regime signals"},
            {"name": "execution_agent", "status": "active", "description": "Tracks execution quality, slippage and fill metrics"},
            {"name": "liquidity_agent", "status": "active", "description": "Monitors stablecoin health, depeg risk and liquidity conditions"},
            {"name": "hyperliquid_agent", "status": "active", "description": "Analyzes orderbook microstructure, spread and depth on Hyperliquid"},
            {"name": "jupiter_agent", "status": "active", "description": "Monitors Jupiter quote freshness, route complexity, price impact and Solana congestion"},
            {"name": "hedging_agent", "status": "active", "description": "Position-aware hedge recommendations based on shock, vol, funding and margin signals"},
        ],
        "total_signals": signal_count,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
