from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

_DEFAULTS = {
    "semis": ["NVDA", "AMD", "INTC", "SMH", "SOXX"],
    "retail_imports": ["NKE", "LULU", "WMT", "TGT", "COST", "HD", "XRT"],
    "industrials": ["CAT", "DE", "BA", "XLI"],
    "china_sensitive": ["KWEB", "FXI", "EEM", "AAPL", "TSLA"],
    "crypto_majors": ["BTC", "ETH", "SOL"],
    "stablecoin_risk": ["USDC", "USDT", "DAI"],
    "high_beta_tech": ["QQQ", "NVDA", "AMD", "TSLA", "AAPL"],
    "portfolio_holdings": ["SPY", "QQQ", "BTC", "SOL"],
}
_STORE: dict[str, dict[str, Any]] = {k: {"id": k, "name": k.replace("_", " ").title(), "assets": v, "risk_profile": k, "created_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()} for k, v in _DEFAULTS.items()}


def list_watchlists() -> dict[str, Any]:
    return {"watchlists": list(_STORE.values()), "count": len(_STORE), "fallback_mode": True, "ts": datetime.now(timezone.utc).isoformat()}


def create_watchlist(body: dict[str, Any]) -> dict[str, Any]:
    wid = body.get("id") or str(uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()
    row = {"id": wid, "name": body.get("name", "Custom Watchlist"), "assets": list(body.get("assets", [])), "risk_profile": body.get("risk_profile", "custom"), "created_at": now, "updated_at": now}
    _STORE[wid] = row
    return row


def update_watchlist(wid: str, body: dict[str, Any]) -> dict[str, Any] | None:
    if wid not in _STORE:
        return None
    _STORE[wid].update({k: v for k, v in body.items() if k in {"name", "assets", "risk_profile"}})
    _STORE[wid]["updated_at"] = datetime.now(timezone.utc).isoformat()
    return _STORE[wid]


def delete_watchlist(wid: str) -> dict[str, Any]:
    existed = _STORE.pop(wid, None) is not None
    return {"id": wid, "deleted": existed, "ts": datetime.now(timezone.utc).isoformat()}
