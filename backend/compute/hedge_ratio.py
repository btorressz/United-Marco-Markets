import logging
import math
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_WINDOW = 30
MIN_OBSERVATIONS = 5


def compute_rolling_correlations(
    returns: dict[str, list[float]],
    window: int = DEFAULT_WINDOW,
) -> dict[str, Any]:
    assets = list(returns.keys())
    correlations = {}

    for i, a1 in enumerate(assets):
        for a2 in assets[i + 1:]:
            r1 = returns.get(a1, [])
            r2 = returns.get(a2, [])
            n = min(len(r1), len(r2), window)
            if n < MIN_OBSERVATIONS:
                correlations[f"{a1}_vs_{a2}"] = {
                    "correlation": None,
                    "sample_size": n,
                    "window": window,
                    "note": f"Insufficient data ({n} < {MIN_OBSERVATIONS})",
                }
                continue

            s1 = r1[-n:]
            s2 = r2[-n:]
            corr = _pearson(s1, s2)
            correlations[f"{a1}_vs_{a2}"] = {
                "correlation": round(corr, 4) if corr is not None else None,
                "sample_size": n,
                "window": window,
            }

    return {
        "correlations": correlations,
        "assets": assets,
        "window": window,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def compute_hedge_ratios(
    asset_returns: list[float],
    hedge_returns: list[float],
    window: int = DEFAULT_WINDOW,
) -> dict[str, Any]:
    n = min(len(asset_returns), len(hedge_returns), window)
    if n < MIN_OBSERVATIONS:
        return {
            "hedge_ratio": None,
            "r_squared": None,
            "hedge_effectiveness": None,
            "confidence": 0.0,
            "sample_size": n,
            "window": window,
            "note": f"Insufficient data ({n} < {MIN_OBSERVATIONS})",
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    y = asset_returns[-n:]
    x = hedge_returns[-n:]

    cov = _covariance(y, x)
    var_x = _variance(x)

    if var_x < 1e-12:
        return {
            "hedge_ratio": 0.0,
            "r_squared": 0.0,
            "hedge_effectiveness": 0.0,
            "confidence": 0.0,
            "sample_size": n,
            "window": window,
            "note": "Zero variance in hedge instrument",
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    beta = cov / var_x

    var_y = _variance(y)
    if var_y < 1e-12:
        r_squared = 0.0
    else:
        corr = _pearson(y, x)
        r_squared = corr * corr if corr is not None else 0.0

    hedge_effectiveness = r_squared

    confidence = min(0.95, 0.4 + (n / window) * 0.3 + r_squared * 0.25)

    return {
        "hedge_ratio": round(beta, 4),
        "r_squared": round(r_squared, 4),
        "hedge_effectiveness": round(hedge_effectiveness, 4),
        "confidence": round(confidence, 4),
        "sample_size": n,
        "window": window,
        "recommended_hedge_leg": _recommend_leg(beta),
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def compute_full_hedge_analysis(
    returns: dict[str, list[float]],
    macro_shock_series: list[float] | None = None,
    window: int = DEFAULT_WINDOW,
) -> dict[str, Any]:
    corr_result = compute_rolling_correlations(returns, window)

    hedge_ratios = {}
    primary_asset = "SOL"
    if primary_asset in returns:
        for hedge_asset in returns:
            if hedge_asset == primary_asset:
                continue
            hr = compute_hedge_ratios(
                returns[primary_asset],
                returns[hedge_asset],
                window,
            )
            hedge_ratios[f"{primary_asset}_hedged_by_{hedge_asset}"] = hr

    macro_correlations = {}
    if macro_shock_series and len(macro_shock_series) >= MIN_OBSERVATIONS:
        for asset in returns:
            r = returns[asset]
            n = min(len(r), len(macro_shock_series), window)
            if n >= MIN_OBSERVATIONS:
                corr = _pearson(r[-n:], macro_shock_series[-n:])
                macro_correlations[asset] = {
                    "correlation_with_macro_shock": round(corr, 4) if corr is not None else None,
                    "sample_size": n,
                }

    best_hedge = None
    best_effectiveness = 0
    for name, hr in hedge_ratios.items():
        eff = hr.get("hedge_effectiveness", 0) or 0
        if eff > best_effectiveness:
            best_effectiveness = eff
            best_hedge = name

    return {
        "correlations": corr_result["correlations"],
        "hedge_ratios": hedge_ratios,
        "macro_correlations": macro_correlations,
        "best_hedge": best_hedge,
        "best_hedge_effectiveness": round(best_effectiveness, 4),
        "window": window,
        "assets": list(returns.keys()),
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _recommend_leg(beta: float) -> str:
    if beta > 0.5:
        return "short_hl_perp"
    elif beta < -0.5:
        return "long_hl_perp"
    elif abs(beta) < 0.2:
        return "spot_reduction"
    else:
        return "drift_perp_hedge"


def _mean(data: list[float]) -> float:
    if not data:
        return 0.0
    return sum(data) / len(data)


def _variance(data: list[float]) -> float:
    if len(data) < 2:
        return 0.0
    m = _mean(data)
    return sum((x - m) ** 2 for x in data) / len(data)


def _covariance(x: list[float], y: list[float]) -> float:
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    mx = _mean(x[:n])
    my = _mean(y[:n])
    return sum((x[i] - mx) * (y[i] - my) for i in range(n)) / n


def _pearson(x: list[float], y: list[float]) -> float | None:
    n = min(len(x), len(y))
    if n < 2:
        return None
    cov = _covariance(x[:n], y[:n])
    sx = math.sqrt(_variance(x[:n]))
    sy = math.sqrt(_variance(y[:n]))
    if sx < 1e-12 or sy < 1e-12:
        return None
    return cov / (sx * sy)
