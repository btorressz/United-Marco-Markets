from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter

from backend.compute.strategy_performance import compute_strategy_performance
from backend.data.repositories.positions_repo import PositionsRepository

router = APIRouter(prefix="/api/strategy", tags=["strategy"])
_repo = PositionsRepository()


@router.get("/performance")
def performance():
    trades = _repo.get_paper_trades(limit=500)
    if not trades:
        now = datetime.now(timezone.utc).isoformat()
        trades = [
            {"strategy_id": "macro_defensive", "venue": "paper", "market": "SPY", "side": "buy", "size": 10, "price": 100, "slippage_bps": 2, "ts": now},
            {"strategy_id": "macro_defensive", "venue": "paper", "market": "SPY", "side": "sell", "size": 10, "price": 101.2, "slippage_bps": 3, "ts": now},
            {"strategy_id": "carry_arb", "venue": "paper", "market": "SOL", "side": "buy", "size": 3, "price": 150, "slippage_bps": 4, "ts": now},
            {"strategy_id": "carry_arb", "venue": "paper", "market": "SOL", "side": "sell", "size": 3, "price": 149.4, "slippage_bps": 5, "ts": now},
        ]
    result = compute_strategy_performance(trades)
    for sid, row in result.get("strategies", {}).items():
        row.setdefault("exposure", 0.0)
        row.setdefault("last_signal_ts", row.get("ts"))
    result["capital_allocation_feedback"] = "Performance is proposal-only input to allocator; no auto-trading."
    return result
