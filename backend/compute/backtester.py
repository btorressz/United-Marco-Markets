import logging
import math
import random
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

_RANDOM_SEED = 42


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _simulate_price_path(
    start_price: float,
    n_steps: int,
    daily_vol: float,
    drift: float,
    seed: int = _RANDOM_SEED,
) -> list[float]:
    rng = random.Random(seed)
    prices = [start_price]
    step_vol = daily_vol / math.sqrt(252)
    step_drift = drift / 252
    for _ in range(n_steps):
        z = rng.gauss(0, 1)
        ret = step_drift + step_vol * z
        prices.append(prices[-1] * (1.0 + ret))
    return prices


def _compute_sharpe(returns: list[float], risk_free_rate: float = 0.04) -> float:
    if len(returns) < 2:
        return 0.0
    n = len(returns)
    mean_r = sum(returns) / n
    variance = sum((r - mean_r) ** 2 for r in returns) / (n - 1)
    std_r = math.sqrt(variance) if variance > 0 else 0.0
    ann_mean = mean_r * 252
    if std_r == 0:
        excess = ann_mean - risk_free_rate
        if excess > 0:
            return 999.0
        if excess < 0:
            return -999.0
        return 0.0
    ann_std = std_r * math.sqrt(252)
    return (ann_mean - risk_free_rate) / ann_std


def _compute_max_drawdown(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = (peak - val) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _compute_var_cvar(returns: list[float], confidence: float = 0.95) -> tuple[float, float]:
    if not returns:
        return 0.0, 0.0
    sorted_r = sorted(returns)
    idx = int((1.0 - confidence) * len(sorted_r))
    var = -sorted_r[max(idx - 1, 0)]
    tail = sorted_r[:max(idx, 1)]
    cvar = -sum(tail) / len(tail) if tail else var
    return round(var, 6), round(cvar, 6)


def run_backtest(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or {}

    window_days = int(_clamp(float(config.get("window_days", 30)), 1, 365))
    initial_capital = float(config.get("initial_capital", 10000.0))
    fee_bps = float(config.get("fee_bps", 10.0))
    slippage_bps = float(config.get("slippage_bps", 5.0))
    funding_rate_daily = float(config.get("funding_rate_daily", 0.0001))
    trade_frequency_days = float(config.get("trade_frequency_days", 1.0))
    strategy = str(config.get("strategy", "momentum"))
    venue = str(config.get("venue", "hyperliquid"))
    start_price = float(config.get("start_price", 150.0))
    daily_vol = float(config.get("daily_vol", 0.04))
    drift = float(config.get("drift", 0.10))

    prices = _simulate_price_path(start_price, window_days, daily_vol, drift)

    cost_per_trade = (fee_bps + slippage_bps) / 10000.0

    trade_interval = max(int(trade_frequency_days), 1)
    positions: list[dict[str, Any]] = []
    equity_curve = [initial_capital]
    capital = initial_capital
    holding = 0.0
    entry_price = 0.0
    wins = 0
    losses = 0
    total_trades = 0
    total_slippage = 0.0
    per_strategy_pnl: dict[str, float] = {"momentum": 0.0, "carry": 0.0, "funding": 0.0}

    daily_returns: list[float] = []

    for i in range(1, window_days + 1):
        price = prices[i]
        prev_price = prices[i - 1]

        if holding != 0.0:
            carry_pnl = holding * prev_price * funding_rate_daily
            capital += carry_pnl
            per_strategy_pnl["funding"] += carry_pnl

        if i % trade_interval == 0:
            if holding != 0.0:
                trade_cost = abs(holding) * price * cost_per_trade
                trade_pnl = holding * (price - entry_price) - trade_cost
                capital += trade_pnl
                total_slippage += abs(holding) * price * (slippage_bps / 10000.0)
                if trade_pnl > 0:
                    wins += 1
                else:
                    losses += 1
                total_trades += 1
                per_strategy_pnl["momentum"] += trade_pnl

                positions.append({
                    "entry": round(entry_price, 4),
                    "exit": round(price, 4),
                    "pnl": round(trade_pnl, 4),
                    "side": "long" if holding > 0 else "short",
                    "day": i,
                })

            if strategy == "momentum":
                if price > prev_price * 1.005:
                    holding = capital / price * 0.5
                    entry_price = price
                elif price < prev_price * 0.995:
                    holding = -(capital / price * 0.5)
                    entry_price = price
                else:
                    holding = 0.0
                    entry_price = 0.0
            elif strategy == "carry_arb":
                if funding_rate_daily > 0:
                    holding = -(capital / price * 0.4)
                    entry_price = price
                else:
                    holding = capital / price * 0.4
                    entry_price = price
            else:
                holding = capital / price * 0.3
                entry_price = price

        daily_return = (capital - equity_curve[-1]) / equity_curve[-1] if equity_curve[-1] > 0 else 0.0
        daily_returns.append(daily_return)
        equity_curve.append(capital)

    if holding != 0.0 and len(prices) > 0:
        final_price = prices[-1]
        trade_cost = abs(holding) * final_price * cost_per_trade
        trade_pnl = holding * (final_price - entry_price) - trade_cost
        capital += trade_pnl
        equity_curve[-1] = capital
        total_slippage += abs(holding) * final_price * (slippage_bps / 10000.0)
        if trade_pnl > 0:
            wins += 1
        else:
            losses += 1
        total_trades += 1

    total_return = (capital - initial_capital) / initial_capital if initial_capital > 0 else 0.0
    sharpe = _compute_sharpe(daily_returns)
    max_dd = _compute_max_drawdown(equity_curve)
    win_rate = wins / total_trades if total_trades > 0 else 0.0
    avg_slippage_bps = (total_slippage / initial_capital * 10000) / total_trades if total_trades > 0 else 0.0
    var_95, cvar_95 = _compute_var_cvar(daily_returns)

    equity_curve_sampled = _downsample(equity_curve, 50)

    return {
        "total_return": round(total_return, 6),
        "total_return_pct": round(total_return * 100, 3),
        "final_capital": round(capital, 4),
        "sharpe_ratio": round(sharpe, 4),
        "max_drawdown": round(max_dd, 6),
        "max_drawdown_pct": round(max_dd * 100, 3),
        "win_rate": round(win_rate, 4),
        "trade_count": total_trades,
        "avg_slippage_bps": round(avg_slippage_bps, 2),
        "var_95": round(var_95, 6),
        "cvar_95": round(cvar_95, 6),
        "equity_curve": [round(v, 2) for v in equity_curve_sampled],
        "per_strategy_pnl": {k: round(v, 4) for k, v in per_strategy_pnl.items()},
        "config": {
            "window_days": window_days,
            "initial_capital": initial_capital,
            "strategy": strategy,
            "venue": venue,
            "fee_bps": fee_bps,
            "slippage_bps": slippage_bps,
            "funding_rate_daily": funding_rate_daily,
        },
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _downsample(series: list[float], max_points: int) -> list[float]:
    if len(series) <= max_points:
        return series
    step = len(series) / max_points
    return [series[int(i * step)] for i in range(max_points)] + [series[-1]]
