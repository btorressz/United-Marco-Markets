import logging
from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.core.state_store import StateStore
from backend.core.event_bus import EventBus, EventType
from backend.compute.monte_carlo import MonteCarloEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/risk/montecarlo", tags=["montecarlo"])

_engine = MonteCarloEngine()
_store = StateStore()
_bus = EventBus()


class MCRequest(BaseModel):
    symbol: str = "SOL"
    horizon_hours: float = Field(4, ge=0.01, le=48)
    n_paths: int = Field(2000, ge=100, le=10000)
    position_size: float = Field(1.0)
    volatility: float | None = None
    current_price: float | None = None


@router.post("/run")
def run_monte_carlo(req: MCRequest):
    price = req.current_price
    if price is None or price <= 0:
        snap = _store.get_snapshot(f"price:{req.symbol.lower()}:pyth")
        if snap and snap.get("price"):
            price = snap["price"]
        else:
            price = 100.0

    vol = req.volatility
    if vol is None:
        vol = 0.65

    shock = _store.get_snapshot("index:latest")
    shock_adj = 0.0
    if shock:
        shock_adj = min(shock.get("shock_score", 0) * 0.1, 0.5)

    funding = 0.0
    fund_snap = _store.get_snapshot("funding:latest")
    if fund_snap:
        funding = fund_snap.get("rate", 0.0)

    margin = abs(req.position_size * price) / 3.0
    liq_price = price * 0.7 if req.position_size > 0 else price * 1.3

    result = _engine.run(
        current_price=price,
        position_size=req.position_size,
        volatility=vol,
        horizon_hours=req.horizon_hours,
        n_paths=req.n_paths,
        funding_rate=funding,
        shock_adjustment=shock_adj,
        margin=margin,
        liq_price=liq_price,
    )
    result["symbol"] = req.symbol

    _store.set_snapshot("montecarlo:latest", result, ttl=300)

    try:
        _bus.emit("MONTE_CARLO_RUN", "montecarlo_engine", {
            "symbol": req.symbol,
            "var_95": result["var_95"],
            "cvar_95": result["cvar_95"],
            "n_paths": req.n_paths,
        })
    except Exception:
        pass

    return result


@router.get("/latest")
def get_latest():
    cached = _store.get_snapshot("montecarlo:latest")
    if cached:
        return cached
    return {"message": "No Monte Carlo results cached. Run a simulation first.", "ts": datetime.now(timezone.utc).isoformat()}
