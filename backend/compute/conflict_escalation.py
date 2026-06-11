from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

HOTSPOTS = [
    {"region": "Middle East", "countries": ["Iran", "Israel", "Saudi Arabia"], "assets": ["USO", "XLE", "XOM", "CVX", "ITA", "GLD"], "sectors": ["Oil", "Defense", "Airlines", "Inflation"]},
    {"region": "Taiwan Strait", "countries": ["China", "Taiwan", "United States"], "assets": ["SMH", "SOXX", "QQQ", "AAPL", "NVDA", "AMD"], "sectors": ["Semiconductors", "Technology"]},
    {"region": "Russia/Ukraine", "countries": ["Russia", "Ukraine", "Europe"], "assets": ["XLE", "DBA", "ITA", "GLD"], "sectors": ["Energy", "Wheat", "Fertilizer", "Defense"]},
    {"region": "Red Sea / Suez", "countries": ["Yemen", "Egypt", "Global"], "assets": ["USO", "XLE", "XRT", "WMT", "NKE"], "sectors": ["Shipping", "Oil", "Retail Imports"]},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _severity(score: float) -> str:
    return "crisis" if score >= 85 else "high" if score >= 70 else "elevated" if score >= 45 else "watch"


def score_conflicts(gdelt: dict[str, Any] | None = None) -> dict[str, Any]:
    degraded = not gdelt
    shock = abs(float((gdelt or {}).get("shock_score", 0.8) or 0.8))
    tone = abs(float((gdelt or {}).get("avg_tone", (gdelt or {}).get("tone", -2.5)) or -2.5))
    volume = float((gdelt or {}).get("event_volume", (gdelt or {}).get("count", 12)) or 12)
    base = min(100.0, 28 + shock * 12 + tone * 4 + min(volume, 100) * 0.25)
    hotspots = []
    for i, h in enumerate(HOTSPOTS):
        score = min(100.0, base + i * 3)
        hotspots.append({**h, "risk_score": round(score, 2), "severity": _severity(score), "reasoning": ["GDELT-style conflict tone/event-volume proxy", "Fallback hotspot map used when live events are unavailable"], "data_quality": "degraded" if degraded else "ok"})
    return {"conflict_score": round(base, 2), "severity": _severity(base), "hotspots": hotspots, "degraded": degraded, "data_quality": "degraded" if degraded else "ok", "timestamp": _now()}


def normalized_conflict_events(conflicts: dict[str, Any]) -> list[dict[str, Any]]:
    events = []
    for h in conflicts.get("hotspots", []):
        events.append({"event_id": f"conflict-{h['region'].lower().replace(' ', '-')}", "event_type": "CONFLICT_ESCALATION", "title": f"{h['region']} escalation watch", "region": h["region"], "countries": h["countries"], "severity": h["severity"], "confidence": 0.62 if conflicts.get("degraded") else 0.78, "source": "GDELT fallback" if conflicts.get("degraded") else "GDELT", "event_timestamp": conflicts.get("timestamp"), "data_timestamp": conflicts.get("timestamp"), "affected_sectors": h["sectors"], "affected_assets": h["assets"], "reasoning": h["reasoning"], "data_quality": h["data_quality"]})
    return events


def conflict_market_impact(conflicts: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for h in conflicts.get("hotspots", []):
        for asset in h["assets"]:
            rows.append({"asset": asset, "region": h["region"], "impact_score": h["risk_score"], "direction": "bullish" if asset in {"GLD", "ITA", "XLE", "XOM", "CVX", "USO"} else "bearish", "reason": f"{h['region']} risk maps to {asset}"})
    return {"impacts": rows, "count": len(rows), "timestamp": _now(), "data_quality": conflicts.get("data_quality", "degraded")}
