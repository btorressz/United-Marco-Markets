import logging
import math
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_ANNUALIZE = 252.0


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _compute_sharpe(returns: list[float], risk_free: float = 0.0) -> float:
    if len(returns) < 2:
        return 0.0
    n = len(returns)
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    std = math.sqrt(variance) if variance > 0 else 0.0
    if std <= 0:
        return 0.0
    daily_rf = risk_free / _ANNUALIZE
    return round((mean - daily_rf) / std * math.sqrt(_ANNUALIZE), 4)


def _compute_max_drawdown(equity: list[float]) -> float:
    if not equity:
        return 0.0
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 6)


def compute_strategy_performance(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return _empty_perf()

    strategies: dict[str, list[dict]] = {}
    for t in trades:
        sid = t.get("strategy_id") or "manual"
        strategies.setdefault(sid, []).append(t)

    results = {}
    for sid, strades in strategies.items():
        results[sid] = _compute_single(sid, strades)

    summary = _make_summary(results)
    return {
        "strategies": results,
        "summary": summary,
        "total_trades": len(trades),
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _compute_single(strategy_id: str, trades: list[dict]) -> dict[str, Any]:
    if not trades:
        return _empty_perf_single(strategy_id)

    sorted_trades = sorted(trades, key=lambda t: t.get("ts") or "")

    buys = [t for t in sorted_trades if (t.get("side") or "").lower() == "buy"]
    sells = [t for t in sorted_trades if (t.get("side") or "").lower() == "sell"]

    trade_pnls: list[float] = []
    matched: list[tuple[dict, dict]] = []

    for sell in sells:
        matching_buy = next(
            (b for b in buys if b.get("market") == sell.get("market") and b.get("venue") == sell.get("venue")),
            None,
        )
        if matching_buy:
            entry = float(matching_buy.get("price") or 0)
            exit_p = float(sell.get("price") or 0)
            size = float(sell.get("size") or 0)
            pnl = (exit_p - entry) * size
            trade_pnls.append(pnl)
            matched.append((matching_buy, sell))

    wins = [p for p in trade_pnls if p > 0]
    losses = [p for p in trade_pnls if p <= 0]
    total_pnl = sum(trade_pnls) if trade_pnls else 0.0
    win_rate = len(wins) / len(trade_pnls) if trade_pnls else 0.0

    prices = [float(t.get("price") or 0) for t in sorted_trades]
    equity: list[float] = []
    running = 0.0
    for pnl in trade_pnls:
        running += pnl
        equity.append(running)

    returns: list[float] = []
    for i in range(1, len(equity)):
        prev = equity[i - 1]
        if prev != 0:
            returns.append((equity[i] - prev) / abs(prev))

    slippages = [float(t.get("slippage_bps") or 0) for t in sorted_trades if t.get("slippage_bps") is not None]
    avg_slippage = sum(slippages) / len(slippages) if slippages else 0.0

    avg_hold_seconds: float | None = None
    hold_times = []
    for buy_t, sell_t in matched:
        try:
            bt = datetime.fromisoformat(str(buy_t.get("ts") or ""))
            st = datetime.fromisoformat(str(sell_t.get("ts") or ""))
            hold_times.append((st - bt).total_seconds())
        except Exception:
            pass
    if hold_times:
        avg_hold_seconds = sum(hold_times) / len(hold_times)

    return {
        "strategy_id": strategy_id,
        "trade_count": len(sorted_trades),
        "matched_trades": len(trade_pnls),
        "total_pnl": round(total_pnl, 4),
        "win_rate": round(win_rate, 4),
        "wins": len(wins),
        "losses": len(losses),
        "max_drawdown": _compute_max_drawdown(equity) if equity else 0.0,
        "sharpe": _compute_sharpe(returns) if returns else 0.0,
        "avg_slippage_bps": round(avg_slippage, 2),
        "avg_holding_seconds": round(avg_hold_seconds, 1) if avg_hold_seconds is not None else None,
        "equity_curve": [round(e, 4) for e in equity],
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _make_summary(results: dict[str, dict]) -> dict[str, Any]:
    if not results:
        return {}
    best = max(results.values(), key=lambda r: r.get("total_pnl", 0.0), default=None)
    worst = min(results.values(), key=lambda r: r.get("total_pnl", 0.0), default=None)
    total_pnl = sum(r.get("total_pnl", 0.0) for r in results.values())
    return {
        "best_strategy": best.get("strategy_id") if best else None,
        "worst_strategy": worst.get("strategy_id") if worst else None,
        "total_pnl_all": round(total_pnl, 4),
        "strategy_count": len(results),
    }


def _empty_perf() -> dict[str, Any]:
    return {
        "strategies": {},
        "summary": {},
        "total_trades": 0,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _empty_perf_single(strategy_id: str) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "trade_count": 0,
        "matched_trades": 0,
        "total_pnl": 0.0,
        "win_rate": 0.0,
        "wins": 0,
        "losses": 0,
        "max_drawdown": 0.0,
        "sharpe": 0.0,
        "avg_slippage_bps": 0.0,
        "avg_holding_seconds": None,
        "equity_curve": [],
        "ts": datetime.now(timezone.utc).isoformat(),
    }
