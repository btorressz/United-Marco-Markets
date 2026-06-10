import logging
import math
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from backend.core.state_store import StateStore
from backend.core.event_bus import EventBus, EventType

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio-risk", tags=["portfolio_risk"])

_store = StateStore()
_bus = EventBus()

_SUMMARY_TTL = 30


def _get_positions() -> list[dict[str, Any]]:
    snap = _store.get_snapshot("execution:positions")
    if snap:
        return snap.get("positions", [])
    return []


def _get_price(market: str) -> float:
    symbol_map = {
        "SOL-PERP": "SOL_USD",
        "BTC-PERP": "BTC_USD",
        "ETH-PERP": "ETH_USD",
    }
    symbol = symbol_map.get(market, "SOL_USD")
    for source in ["pyth", "kraken", "coingecko"]:
        snap = _store.get_snapshot(f"price:{source}:{symbol}")
        if snap and "price" in snap:
            return float(snap["price"])
    return 0.0


def _get_vol(market: str) -> float:
    symbol_map = {
        "SOL-PERP": "SOL_USD",
        "BTC-PERP": "BTC_USD",
        "ETH-PERP": "ETH_USD",
    }
    symbol = symbol_map.get(market, "SOL_USD")
    for source in ["pyth", "kraken"]:
        snap = _store.get_snapshot(f"price:{source}:{symbol}")
        if snap and "vol_annualized" in snap:
            return float(snap["vol_annualized"])
    return 0.45


def _compute_summary() -> dict[str, Any]:
    positions = _get_positions()

    total_long = 0.0
    total_short = 0.0
    venue_exposure: dict[str, float] = {}
    asset_contributions: list[dict[str, Any]] = []
    equity_curve: list[float] = []
    total_pnl = 0.0

    for pos in positions:
        market = pos.get("market", "UNKNOWN")
        size = float(pos.get("size", 0.0))
        entry = float(pos.get("entry_price", 0.0))
        side = pos.get("side", "long")
        venue = pos.get("venue", "paper")

        price = _get_price(market) or entry
        notional = abs(size) * price
        vol = _get_vol(market)
        risk_contrib = notional * vol

        pnl = 0.0
        if entry > 0 and price > 0:
            if side == "long":
                pnl = size * (price - entry)
                total_long += notional
            else:
                pnl = -size * (price - entry)
                total_short += notional

        total_pnl += pnl
        venue_exposure[venue] = venue_exposure.get(venue, 0.0) + notional

        asset_contributions.append({
            "market": market,
            "venue": venue,
            "side": side,
            "notional": round(notional, 4),
            "pnl": round(pnl, 4),
            "risk_contribution": round(risk_contrib, 4),
            "vol_estimate": round(vol, 4),
        })

    total_exposure = total_long + total_short
    net_exposure = total_long - total_short
    stable_snap = _store.get_snapshot("stablecoin:health:latest")
    stable_alloc = 0.0
    if stable_snap:
        stable_alloc = stable_snap.get("total_value_usd", 0.0)

    total_portfolio = total_exposure + stable_alloc if total_exposure + stable_alloc > 0 else 1.0
    concentration_risk = max(
        v / total_portfolio for v in venue_exposure.values()
    ) if venue_exposure else 0.0

    max_notional_position = max(
        (a["notional"] for a in asset_contributions), default=0.0
    )
    concentration_by_asset = max_notional_position / total_portfolio if total_portfolio > 0 else 0.0

    var_estimate = total_exposure * 0.45 * (1.65 / math.sqrt(252))
    cvar_estimate = var_estimate * 1.35
    liquidity_adj_risk = var_estimate * (1.0 + concentration_risk * 0.5)

    drawdown = 0.0

    warnings: list[str] = []
    if concentration_risk > 0.6:
        warnings.append(f"High venue concentration: {concentration_risk:.1%} in one venue")
    if concentration_by_asset > 0.5:
        warnings.append(f"High asset concentration: {concentration_by_asset:.1%} in one asset")
    if total_exposure > total_portfolio * 2.0:
        warnings.append("Leverage > 2x detected")
    if len(positions) == 0:
        warnings.append("No open positions")

    result = {
        "total_exposure": round(total_exposure, 4),
        "long_exposure": round(total_long, 4),
        "short_exposure": round(total_short, 4),
        "net_exposure": round(net_exposure, 4),
        "stablecoin_allocation": round(stable_alloc, 4),
        "total_pnl": round(total_pnl, 4),
        "var_95": round(var_estimate, 4),
        "cvar_95": round(cvar_estimate, 4),
        "max_drawdown": round(drawdown, 4),
        "current_drawdown": round(drawdown, 4),
        "concentration_risk_venue": round(concentration_risk, 4),
        "concentration_risk_asset": round(concentration_by_asset, 4),
        "liquidity_adjusted_risk": round(liquidity_adj_risk, 4),
        "venue_exposure": {k: round(v, 4) for k, v in venue_exposure.items()},
        "position_count": len(positions),
        "warnings": warnings,
        "ts": datetime.now(timezone.utc).isoformat(),
    }

    _bus.emit(
        EventType.PORTFOLIO_RISK_UPDATE,
        source="portfolio_risk_routes",
        payload={
            "total_exposure": result["total_exposure"],
            "var_95": result["var_95"],
            "concentration_risk_venue": result["concentration_risk_venue"],
            "warnings": warnings,
        },
    )

    return result


@router.get("/summary")
def get_portfolio_risk_summary():
    cached = _store.get_snapshot("desk:portfolio_risk:summary")
    if cached:
        return cached

    result = _compute_summary()
    _store.set_snapshot("desk:portfolio_risk:summary", result, ttl=_SUMMARY_TTL)
    return result


@router.get("/contributions")
def get_risk_contributions():
    positions = _get_positions()
    contributions = []

    for pos in positions:
        market = pos.get("market", "UNKNOWN")
        size = float(pos.get("size", 0.0))
        entry = float(pos.get("entry_price", 0.0))
        side = pos.get("side", "long")
        venue = pos.get("venue", "paper")

        price = _get_price(market) or entry
        notional = abs(size) * price
        vol = _get_vol(market)
        risk_contrib = notional * vol

        contributions.append({
            "market": market,
            "venue": venue,
            "side": side,
            "notional": round(notional, 4),
            "risk_contribution": round(risk_contrib, 4),
            "risk_contribution_pct": 0.0,
            "vol_estimate": round(vol, 4),
        })

    total_risk = sum(c["risk_contribution"] for c in contributions)
    for c in contributions:
        c["risk_contribution_pct"] = round(
            c["risk_contribution"] / total_risk if total_risk > 0 else 0.0, 4
        )

    return {
        "contributions": contributions,
        "total_risk": round(total_risk, 4),
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/exposures")
def get_exposures():
    positions = _get_positions()
    venue_exp: dict[str, float] = {}
    asset_exp: dict[str, float] = {}

    for pos in positions:
        market = pos.get("market", "UNKNOWN")
        size = float(pos.get("size", 0.0))
        entry = float(pos.get("entry_price", 0.0))
        venue = pos.get("venue", "paper")

        price = _get_price(market) or entry
        notional = abs(size) * price

        venue_exp[venue] = venue_exp.get(venue, 0.0) + notional
        asset_exp[market] = asset_exp.get(market, 0.0) + notional

    return {
        "by_venue": {k: round(v, 4) for k, v in venue_exp.items()},
        "by_asset": {k: round(v, 4) for k, v in asset_exp.items()},
        "position_count": len(positions),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
