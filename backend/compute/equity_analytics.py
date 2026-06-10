from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except Exception:
        return default


def pct_change(values: list[float], lookback: int) -> float:
    if len(values) <= lookback or values[-lookback - 1] == 0:
        return 0.0
    return values[-1] / values[-lookback - 1] - 1.0


def realized_volatility(closes: list[float], lookback: int = 20) -> float:
    vals = closes[-(lookback + 1):]
    if len(vals) < 3:
        return 0.0
    rets = [vals[i] / vals[i - 1] - 1.0 for i in range(1, len(vals)) if vals[i - 1] > 0]
    if len(rets) < 2:
        return 0.0
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return round(math.sqrt(var) * math.sqrt(252), 6)


def max_drawdown(closes: list[float]) -> float:
    peak = 0.0
    dd = 0.0
    for c in closes:
        peak = max(peak, c)
        if peak > 0:
            dd = max(dd, (peak - c) / peak)
    return round(dd, 6)


def moving_average(closes: list[float], window: int) -> float:
    vals = closes[-window:]
    return round(sum(vals) / len(vals), 4) if vals else 0.0


def rsi(closes: list[float], window: int = 14) -> float:
    if len(closes) <= window:
        return 50.0
    gains, losses = [], []
    for i in range(len(closes) - window, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(abs(min(delta, 0.0)))
    avg_gain = sum(gains) / window
    avg_loss = sum(losses) / window
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def beta_proxy(closes: list[float], spy_closes: list[float]) -> float:
    n = min(len(closes), len(spy_closes), 60)
    if n < 5:
        return 1.0
    a = closes[-n:]
    b = spy_closes[-n:]
    ra = [a[i] / a[i - 1] - 1.0 for i in range(1, n) if a[i - 1] > 0 and b[i - 1] > 0]
    rb = [b[i] / b[i - 1] - 1.0 for i in range(1, n) if a[i - 1] > 0 and b[i - 1] > 0]
    if len(ra) != len(rb) or len(ra) < 3:
        return 1.0
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    var = sum((y - mb) ** 2 for y in rb)
    return round(cov / var, 4) if var > 0 else 1.0


def analyze_history(ticker: str, history: list[dict[str, Any]], spy_history: list[dict[str, Any]] | None = None, sector: str = "Unknown") -> dict[str, Any]:
    rows = [r for r in history if _safe_float(r.get("close")) > 0]
    closes = [_safe_float(r.get("close")) for r in rows]
    volumes = [_safe_float(r.get("volume")) for r in rows]
    last = rows[-1] if rows else {"close": 0, "volume": 0, "ts": datetime.now(timezone.utc).isoformat()}
    spy_closes = [_safe_float(r.get("close")) for r in (spy_history or []) if _safe_float(r.get("close")) > 0]
    spy_1m = pct_change(spy_closes, min(21, len(spy_closes) - 1)) if spy_closes else 0.0
    one_m = pct_change(closes, min(21, len(closes) - 1)) if closes else 0.0
    avg_vol = sum(volumes[-20:]) / len(volumes[-20:]) if volumes else 0.0
    return {
        "ticker": ticker.upper(),
        "sector": sector,
        "price": round(_safe_float(last.get("close")), 4),
        "daily_return": round(pct_change(closes, 1), 6),
        "return_5d": round(pct_change(closes, min(5, len(closes) - 1)), 6),
        "return_1m": round(one_m, 6),
        "realized_volatility": realized_volatility(closes),
        "max_drawdown": max_drawdown(closes),
        "ma_20": moving_average(closes, min(20, len(closes))),
        "ma_50": moving_average(closes, min(50, len(closes))),
        "rsi": rsi(closes),
        "beta_proxy": beta_proxy(closes, spy_closes),
        "relative_strength_vs_spy": round(one_m - spy_1m, 6),
        "volume": int(_safe_float(last.get("volume"))),
        "avg_volume_20d": int(avg_vol),
        "volume_vs_avg": round((_safe_float(last.get("volume")) / avg_vol) if avg_vol > 0 else 1.0, 4),
        "data_ts": last.get("ts"),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
