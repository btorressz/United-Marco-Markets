from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_IMPORT_EXPORT = {"Autos": .85, "Apparel": .82, "Retail": .70, "Machinery": .80, "Aerospace": .72, "Materials": .78, "Steel": .86, "Semiconductors": .74, "Technology": .58, "China Internet": .90, "China Large Cap": .92, "Emerging Markets": .68}


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def score_asset_sensitivity(asset: dict[str, Any], tariff_index_change: float = 0.0, gdelt_shock: float = 0.0, degraded: bool = False) -> dict[str, Any]:
    sector = asset.get("sector", "Unknown")
    import_export = _IMPORT_EXPORT.get(sector, .45)
    rel_weak = _clamp(max(0.0, -float(asset.get("relative_strength_vs_spy", 0.0))) * 9)
    vol = _clamp(float(asset.get("realized_volatility", 0.0)) / .75)
    drawdown = _clamp(float(asset.get("max_drawdown", 0.0)) * 3)
    volume = _clamp(max(0.0, float(asset.get("volume_vs_avg", 1.0)) - 1.0) / 2)
    tariff = _clamp(abs(tariff_index_change) / 25.0)
    gdelt = _clamp(abs(gdelt_shock) / 3.0)
    score = .18 * import_export + .18 * tariff + .14 * gdelt + .16 * rel_weak + .14 * vol + .12 * drawdown + .08 * volume
    beta = round(0.35 + score * 1.8, 4)
    reasoning = [f"sector/import-export sensitivity {import_export:.2f} for {sector}", f"tariff change component {tariff:.2f}", f"GDELT shock component {gdelt:.2f}", f"market reaction: relative weakness {rel_weak:.2f}, vol {vol:.2f}, drawdown {drawdown:.2f}, volume {volume:.2f}"]
    return {"ticker": asset.get("ticker"), "tariff_beta": beta, "macro_sensitivity_score": round(score * 100, 2), "severity": "high" if score >= .65 else "medium" if score >= .4 else "low", "degraded": degraded or bool(asset.get("degraded")), "reasoning": reasoning, "components": {"import_export": import_export, "tariff_change": tariff, "gdelt_shock": gdelt, "relative_weakness": rel_weak, "volatility": vol, "drawdown": drawdown, "volume_spike": volume}, "ts": datetime.now(timezone.utc).isoformat()}


def score_assets(assets: list[dict[str, Any]], tariff_index_change: float = 0.0, gdelt_shock: float = 0.0, degraded: bool = False) -> dict[str, Any]:
    rows = [score_asset_sensitivity(a, tariff_index_change, gdelt_shock, degraded) for a in assets]
    return {"assets": rows, "degraded": degraded or any(r["degraded"] for r in rows), "ts": datetime.now(timezone.utc).isoformat()}
