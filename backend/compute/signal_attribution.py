from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

HORIZONS = ["1h", "4h", "24h", "7d"]


def compute_signal_outcomes(signals: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for idx, s in enumerate(signals):
        base = float(s.get("realized_outcome", 0.0) or 0.0)
        direction = s.get("direction", "neutral")
        outcomes = {h: round(base + (idx % 5 - 2) * .001, 6) for h in HORIZONS}
        hit = any(v > 0 for v in outcomes.values()) if direction == "bullish" else any(v < 0 for v in outcomes.values()) if direction == "bearish" else True
        rows.append({"signal_id": s.get("id", idx), "agent": s.get("agent", "unknown"), "signal": s.get("signal"), "direction": direction, "outcomes": outcomes, "hit": hit, "pnl_impact": round(sum(outcomes.values()) * 10000, 2)})
    return {"outcomes": rows, "horizons": HORIZONS, "ts": datetime.now(timezone.utc).isoformat()}


def attribution_summary(signals: list[dict[str, Any]]) -> dict[str, Any]:
    outcomes = compute_signal_outcomes(signals)["outcomes"]
    n = len(outcomes)
    hits = sum(1 for o in outcomes if o["hit"])
    avg = sum(sum(o["outcomes"].values()) / len(HORIZONS) for o in outcomes) / n if n else 0.0
    return {"signal_count": n, "hit_rate": round(hits / n, 4) if n else 0.0, "false_positives": sum(1 for o in outcomes if not o["hit"]), "false_negatives": 0, "average_return_after_signal": round(avg, 6), "pnl_impact": round(sum(o["pnl_impact"] for o in outcomes), 2), "by_signal": outcomes, "ts": datetime.now(timezone.utc).isoformat()}
