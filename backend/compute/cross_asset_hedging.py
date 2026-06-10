from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def recommend_cross_asset_hedges(state: dict[str, Any] | None = None) -> dict[str, Any]:
    s = state or {}
    tariff_beta = float(s.get("tariff_beta", .65) or .65)
    equity_dd = float(s.get("equity_drawdown", -.025) or 0)
    crypto_dd = float(s.get("crypto_drawdown", -.02) or 0)
    stable_health = float(s.get("stable_health", .98) or .98)
    recs = []
    if tariff_beta > .6:
        recs.append({"asset": "high tariff-beta equities", "action": "reduce_exposure", "confidence": .78, "reason": "Tariff beta is elevated"})
        recs.append({"asset": "QQQ/SMH/XRT/SPY", "action": "preview_index_or_sector_hedge", "confidence": .72, "reason": "Use liquid ETF hedges for technology/retail/import sensitivity"})
    if equity_dd < -.02 and crypto_dd < -.015:
        recs.append({"asset": "crypto majors", "action": "reduce_beta_or_raise_cash", "confidence": .70, "reason": "Equity risk-off is coincident with crypto weakness"})
    if stable_health > .97:
        recs.append({"asset": "cash/stables", "action": "rotate_defensive_buffer", "confidence": .66, "reason": "Stablecoin health is acceptable for defensive buffer"})
    else:
        recs.append({"asset": "cash", "action": "prefer_cash_over_stables", "confidence": .74, "reason": "Stablecoin health is degraded"})
    return {"recommendations": recs, "proposal_only": True, "auto_trade": False, "ts": datetime.now(timezone.utc).isoformat()}
