from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from backend.core.state_store import StateStore
from backend.ingest.yfinance_ingest import EQUITY_INDEX_ETFS, SECTOR_ETFS, TARIFF_SENSITIVE, EQUITY_UNIVERSE, SECTORS, fetch_history, fetch_quote
from backend.ingest.stooq_ingest import fetch_history as fetch_stooq_history
from backend.compute.equity_analytics import analyze_history
from backend.compute.equity_tariff_exposure import score_universe
from backend.agents.equity_risk_agent import EquityRiskAgent
from backend.agents.tariff_exposure_agent import TariffExposureAgent
from backend.agents.sector_rotation_agent import SectorRotationAgent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/equities", tags=["equities"])
_store = StateStore()
_risk_agent = EquityRiskAgent()
_tariff_agent = TariffExposureAgent()
_sector_agent = SectorRotationAgent()


def _history(ticker: str, provider: str = "yfinance") -> dict[str, Any]:
    try:
        if provider == "stooq":
            return fetch_stooq_history(ticker)
        return fetch_history(ticker)
    except Exception as exc:
        logger.warning("Equity history failed for %s", ticker, exc_info=True)
        return fetch_history(ticker) | {"degraded": True, "error": str(exc)}


def _analytics_for(ticker: str, spy_hist: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    h = _history(ticker)
    if h.get("degraded"):
        alt = fetch_stooq_history(ticker)
        if not alt.get("degraded"):
            h = alt
    spy = spy_hist if spy_hist is not None else (_history("SPY").get("history") or [])
    row = analyze_history(ticker, h.get("history") or [], spy, SECTORS.get(ticker.upper(), "Unknown"))
    row["provider_status"] = h.get("provider_status", {})
    row["degraded"] = h.get("degraded", False)
    return row


def _wits_gdelt() -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    warnings = []
    wits = _store.get_snapshot("wits:tariff:USA:ALL:ALL") or _store.get_snapshot("wits:latest")
    gdelt = _store.get_snapshot("gdelt:latest")
    if not wits:
        warnings.append("WITS unavailable; tariff pressure uses safe default")
    if not gdelt:
        warnings.append("GDELT unavailable; sentiment shock uses safe default")
    return wits, gdelt, warnings


def _overview_rows() -> list[dict[str, Any]]:
    spy_hist = _history("SPY").get("history") or []
    return [_analytics_for(t, spy_hist) for t in EQUITY_UNIVERSE]


@router.get("/watchlist")
def watchlist():
    return {"index_etfs": EQUITY_INDEX_ETFS, "sector_etfs": SECTOR_ETFS, "tariff_sensitive": TARIFF_SENSITIVE, "universe": EQUITY_UNIVERSE, "ts": datetime.now(timezone.utc).isoformat()}


@router.get("/quote/{ticker}")
def quote(ticker: str):
    try:
        return fetch_quote(ticker)
    except Exception as exc:
        logger.warning("Quote failed for %s", ticker, exc_info=True)
        return fetch_quote(ticker) | {"degraded": True, "error": str(exc)}


@router.get("/history/{ticker}")
def history(ticker: str, provider: str = "yfinance"):
    return _history(ticker, provider=provider)


@router.get("/overview")
def overview():
    rows = _overview_rows()
    return {
        "status": "degraded" if any(r.get("degraded") for r in rows) else "ok",
        "market_overview": [r for r in rows if r["ticker"] in EQUITY_INDEX_ETFS],
        "sector_etfs": [r for r in rows if r["ticker"] in SECTOR_ETFS],
        "tariff_watchlist": [r for r in rows if r["ticker"] in TARIFF_SENSITIVE],
        "provider_status": {
            "yfinance": {"status": "research_mvp", "note": "No API key required; not institutional-grade"},
            "Stooq": {"status": "fallback_eod"},
            "mock_demo_equity_fallback": {"status": "available"},
        },
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/tariff-exposure")
def tariff_exposure():
    rows = _overview_rows()
    wits, gdelt, warnings = _wits_gdelt()
    result = score_universe(rows, wits, gdelt)
    result["warnings"] = warnings
    return result


@router.get("/risk")
def risk():
    rows = _overview_rows()
    exposure = tariff_exposure().get("scores", [])
    signals = _risk_agent.evaluate(rows) + _tariff_agent.evaluate(exposure)
    return {"signals": signals, "signal_count": len(signals), "ts": datetime.now(timezone.utc).isoformat()}


@router.get("/sector-rotation")
def sector_rotation():
    rows = _overview_rows()
    signals = _sector_agent.evaluate(rows)
    sectors: dict[str, list[float]] = {}
    for r in rows:
        sectors.setdefault(r.get("sector", "Unknown"), []).append(float(r.get("return_5d", 0.0)))
    summary = [{"sector": k, "avg_5d_return": round(sum(v) / len(v), 6), "count": len(v)} for k, v in sectors.items()]
    summary.sort(key=lambda x: x["avg_5d_return"])
    return {"sectors": summary, "signals": signals, "ts": datetime.now(timezone.utc).isoformat()}


@router.get("/cross-asset")
def cross_asset():
    rows = {r["ticker"]: r for r in [_analytics_for(t) for t in ["SPY", "QQQ", "IWM"]]}
    crypto = {"BTC": _store.get_snapshot("price:kraken:BTC_USD") or {}, "ETH": _store.get_snapshot("price:kraken:ETH_USD") or {}, "SOL": _store.get_snapshot("price:pyth:SOL_USD") or {}}
    tariff = _store.get_snapshot("index:latest") or _store.get_snapshot("desk:index:latest") or {}
    gdelt = _store.get_snapshot("gdelt:latest") or {}
    equity_vol = sum(float(r.get("realized_volatility", 0.0)) for r in rows.values()) / max(1, len(rows))
    tariff_level = float(tariff.get("tariff_index", tariff.get("value", 35.0)) or 35.0)
    risk_off = min(100.0, max(0.0, tariff_level * 0.55 + equity_vol * 55 + max(0.0, -rows["SPY"].get("return_5d", 0.0)) * 400))
    return {
        "risk_on_off_score": round(100 - risk_off, 2),
        "regime": "risk_off" if risk_off >= 55 else "risk_on" if risk_off <= 35 else "neutral",
        "equities": rows,
        "crypto": crypto,
        "equity_volatility": round(equity_vol, 6),
        "crypto_volatility_proxy": 0.65,
        "tariff_index": tariff_level,
        "gdelt_tone": gdelt.get("avg_tone", gdelt.get("tone", 0.0)),
        "comparisons": ["SPY/QQQ/IWM vs BTC/ETH/SOL", "tariff index vs equity drawdown", "GDELT tone vs sector returns"],
        "ts": datetime.now(timezone.utc).isoformat(),
    }
