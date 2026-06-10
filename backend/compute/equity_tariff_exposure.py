from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SECTOR_SENSITIVITY = {
    "Autos": 0.90, "Apparel": 0.85, "Retail": 0.70, "Machinery": 0.82, "Aerospace": 0.75,
    "Materials": 0.80, "Steel": 0.88, "Semiconductors": 0.72, "Technology": 0.62,
    "China Internet": 0.90, "China Large Cap": 0.92, "Emerging Markets": 0.68, "Industrials": 0.70,
    "Consumer Discretionary": 0.72, "Energy": 0.45, "Financials": 0.25, "Health Care": 0.25,
    "Broad Market": 0.45,
}


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def score_equity_exposure(analytics: dict[str, Any], wits: dict[str, Any] | None = None, gdelt: dict[str, Any] | None = None) -> dict[str, Any]:
    sector = analytics.get("sector", "Unknown")
    sector_score = SECTOR_SENSITIVITY.get(sector, 0.50)
    wits_pressure = _clamp(float((wits or {}).get("tariff_pressure", (wits or {}).get("value", 35.0))) / 100.0)
    gdelt_shock = _clamp(abs(float((gdelt or {}).get("shock_score", (gdelt or {}).get("tone_shock", 0.25)))) / 3.0)
    price_reaction = _clamp(max(0.0, -float(analytics.get("return_5d", 0.0))) * 8.0)
    volume_spike = _clamp(max(0.0, float(analytics.get("volume_vs_avg", 1.0)) - 1.0) / 2.0)
    vol_spike = _clamp(float(analytics.get("realized_volatility", 0.0)) / 0.80)
    rel_weak = _clamp(max(0.0, -float(analytics.get("relative_strength_vs_spy", 0.0))) * 10.0)
    country_supply = 0.85 if analytics.get("ticker") in {"AAPL", "TSLA", "NKE", "LULU", "KWEB", "FXI", "EEM"} else 0.55
    import_export = 0.85 if sector in {"Autos", "Apparel", "Retail", "Machinery", "Materials", "Steel", "Semiconductors"} else 0.45
    degraded = not wits or not gdelt
    score = (
        0.20 * sector_score + 0.13 * country_supply + 0.12 * import_export + 0.15 * wits_pressure +
        0.12 * gdelt_shock + 0.10 * price_reaction + 0.06 * volume_spike + 0.06 * vol_spike + 0.06 * rel_weak
    )
    severity = "high" if score >= 0.70 else "medium" if score >= 0.45 else "low"
    reasoning = [
        f"sector sensitivity {sector_score:.2f} for {sector}",
        f"supply-chain sensitivity {country_supply:.2f}",
        f"WITS tariff pressure {wits_pressure:.2f}" + (" (default)" if not wits else ""),
        f"GDELT shock/tone {gdelt_shock:.2f}" + (" (default)" if not gdelt else ""),
        f"price/volume reaction components: 5d weakness {price_reaction:.2f}, relative weakness {rel_weak:.2f}, volume spike {volume_spike:.2f}",
    ]
    return {
        "ticker": analytics.get("ticker"),
        "score": round(_clamp(score) * 100, 2),
        "severity": severity,
        "degraded": degraded,
        "components": {
            "sector_sensitivity": sector_score, "country_supply_chain": country_supply, "import_export": import_export,
            "wits_tariff_pressure": wits_pressure, "gdelt_sentiment_shock": gdelt_shock, "stock_price_reaction": price_reaction,
            "volume_spike": volume_spike, "volatility_spike": vol_spike, "relative_weakness_vs_spy": rel_weak,
        },
        "reasoning": reasoning,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def score_universe(analytics_rows: list[dict[str, Any]], wits: dict[str, Any] | None = None, gdelt: dict[str, Any] | None = None) -> dict[str, Any]:
    scores = [score_equity_exposure(row, wits, gdelt) for row in analytics_rows]
    return {"scores": scores, "degraded": any(s["degraded"] for s in scores), "ts": datetime.now(timezone.utc).isoformat()}
