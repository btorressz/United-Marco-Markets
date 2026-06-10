from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


def correlation(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n < 3:
        return 0.0
    x, y = a[-n:], b[-n:]
    mx, my = sum(x) / n, sum(y) / n
    cov = sum((i - mx) * (j - my) for i, j in zip(x, y))
    vx = sum((i - mx) ** 2 for i in x)
    vy = sum((j - my) ** 2 for j in y)
    if vx <= 0 or vy <= 0:
        return 0.0
    return round(cov / math.sqrt(vx * vy), 4)


def compute_correlations(series: dict[str, list[float]]) -> dict[str, Any]:
    names = list(series.keys())
    matrix = []
    for a in names:
        row = {"asset": a}
        for b in names:
            row[b] = 1.0 if a == b else correlation(series.get(a, []), series.get(b, []))
        matrix.append(row)
    return {"assets": names, "matrix": matrix, "degraded": len(names) < 3, "ts": datetime.now(timezone.utc).isoformat()}


def demo_series() -> dict[str, list[float]]:
    base = [i / 100 for i in range(30)]
    return {"tariff_index": base, "gdelt_shock": [x * .8 for x in base], "SPY": [-x * .6 for x in base], "QQQ": [-x * .75 for x in base], "SMH": [-x * .9 for x in base], "BTC": [-x * .4 for x in base], "SOL": [-x * .55 for x in base], "stablecoin_stress": [x * .25 for x in base]}


def detect_contagion(metrics: dict[str, float] | None = None) -> dict[str, Any]:
    m = metrics or {}
    paths = []
    def add(name: str, active: bool, severity: float, reason: str):
        paths.append({"path": name, "active": active, "severity": round(max(0.0, min(1.0, severity)), 4), "reason": reason})
    tariff = float(m.get("tariff_shock", .65))
    equity = float(m.get("equity_return", -.025))
    crypto = float(m.get("crypto_return", -.018))
    stable = float(m.get("stablecoin_depeg_bps", 8.0))
    semis = float(m.get("semiconductor_return", -.035))
    add("tariff shock → equity weakness", tariff > .5 and equity < -.01, tariff * abs(equity) * 20, "Tariff pressure coincides with broad equity weakness")
    add("equity risk-off → crypto risk-off", equity < -.015 and crypto < -.01, abs(equity + crypto) * 12, "Equity weakness is spilling into crypto majors")
    add("stablecoin stress → crypto volatility", stable > 5, stable / 50, "Stablecoin depeg/stress can amplify crypto volatility")
    add("semiconductor weakness → QQQ pressure", semis < -.02, abs(semis) * 12, "SMH/SOXX weakness pressures QQQ and high-beta tech")
    score = sum(p["severity"] for p in paths if p["active"]) / max(1, len(paths))
    return {"contagion_score": round(score * 100, 2), "regime": "contagion" if score > .35 else "watch" if score > .15 else "contained", "paths": paths, "ts": datetime.now(timezone.utc).isoformat()}
