from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _event_id(kind: str, ts: str, title: str) -> str:
    return hashlib.sha1(f"{kind}|{ts}|{title}".encode()).hexdigest()[:12]


def build_macro_events(wits: dict[str, Any] | None = None, gdelt: dict[str, Any] | None = None, limit: int = 25) -> dict[str, Any]:
    """Build a fail-open macro/trade event timeline from WITS/GDELT snapshots.

    When live snapshots are absent, deterministic demo events are returned with
    degraded=True so the UI and downstream analytics still have a stable shape.
    """
    now = _now()
    degraded = not wits or not gdelt
    warnings: list[str] = []
    if not wits:
        warnings.append("WITS tariff updates unavailable; using demo tariff event")
    if not gdelt:
        warnings.append("GDELT shock feed unavailable; using demo headline events")

    raw: list[dict[str, Any]] = []
    if wits:
        ts = str(wits.get("ts") or wits.get("updated_at") or now.isoformat())
        pressure = float(wits.get("tariff_pressure", wits.get("value", 35.0)) or 35.0)
        raw.append({"type": "wits_tariff_update", "title": "WITS tariff pressure update", "severity": "high" if pressure >= 70 else "medium" if pressure >= 45 else "low", "score": pressure, "source": "WITS", "ts": ts, "details": wits})
    if gdelt:
        ts = str(gdelt.get("ts") or now.isoformat())
        shock = abs(float(gdelt.get("shock_score", gdelt.get("tone_shock", 0.0)) or 0.0))
        raw.append({"type": "gdelt_shock_spike", "title": "GDELT trade/geopolitical shock", "severity": "high" if shock >= 1.5 else "medium" if shock >= 0.5 else "low", "score": shock, "source": "GDELT", "ts": ts, "details": gdelt})

    if not raw:
        demo = [
            ("tariff_change", "Demo tariff change watch", 62.0, "WITS/GDELT fallback", 2),
            ("trade_war_headline", "Demo trade-war headline cluster", 0.9, "GDELT fallback", 1),
            ("sanctions", "Demo sanctions watch item", 0.55, "news fallback", 0),
        ]
        for typ, title, score, source, days in demo:
            ts = (now - timedelta(days=days)).isoformat()
            raw.append({"type": typ, "title": title, "severity": "medium", "score": score, "source": source, "ts": ts, "details": {"demo": True}})

    events = []
    for item in sorted(raw, key=lambda x: x.get("ts", ""), reverse=True)[: max(1, min(limit, 100))]:
        events.append({**item, "id": _event_id(item["type"], item["ts"], item["title"]), "degraded": degraded})
    return {"events": events, "count": len(events), "degraded": degraded, "warnings": warnings, "ts": now.isoformat()}


def compute_event_reaction(event: dict[str, Any], market_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    market_snapshot = market_snapshot or {}
    score = float(event.get("score", 0.0) or 0.0)
    sev_mult = {"low": 0.4, "medium": 0.75, "high": 1.15}.get(event.get("severity"), 0.75)
    tariff_pressure = min(1.0, score / 100.0 if score > 3 else score / 3.0)
    equity_reaction = -0.012 * sev_mult - tariff_pressure * 0.018
    crypto_reaction = -0.008 * sev_mult - tariff_pressure * 0.010
    stable_stress = tariff_pressure * 0.12
    funding_shift = -tariff_pressure * 4.0
    basis_shift = tariff_pressure * 18.0
    assets = {}
    for ticker, beta in {"SPY": 1.0, "QQQ": 1.25, "IWM": 1.35, "AAPL": 1.15, "TSLA": 1.55, "NVDA": 1.35, "CAT": 1.25, "NKE": 1.20}.items():
        assets[ticker] = {"estimated_return": round(equity_reaction * beta, 6), "reaction": "weakness" if equity_reaction < 0 else "strength"}
    for ticker, beta in {"BTC": 1.0, "ETH": 1.10, "SOL": 1.35}.items():
        assets[ticker] = {"estimated_return": round(crypto_reaction * beta, 6), "reaction": "risk_off"}
    return {"event_id": event.get("id"), "assets": assets, "stablecoin_health_impact": round(stable_stress, 4), "funding_bps_impact": round(funding_shift, 2), "basis_bps_impact": round(basis_shift, 2), "degraded": bool(event.get("degraded")) or not bool(market_snapshot), "ts": _now().isoformat()}


def compute_impact(events: list[dict[str, Any]], market_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    reactions = [compute_event_reaction(e, market_snapshot) for e in events]
    avg_spy = sum(r["assets"].get("SPY", {}).get("estimated_return", 0.0) for r in reactions) / len(reactions) if reactions else 0.0
    return {"reactions": reactions, "summary": {"event_count": len(events), "avg_spy_reaction": round(avg_spy, 6), "risk_bias": "risk_off" if avg_spy < -0.005 else "neutral"}, "ts": _now().isoformat()}
