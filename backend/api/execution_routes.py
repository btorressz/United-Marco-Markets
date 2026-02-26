import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.schemas import ExecutionStatusResponse
from backend.execution.router import ExecutionRouter
from backend.execution.jupiter_exec import JupiterExecutor
from backend.data.repositories.positions_repo import PositionsRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/execution", tags=["execution"])

_exec_router = ExecutionRouter()
_jupiter = JupiterExecutor()
_positions_repo = PositionsRepository()


class OrderRequest(BaseModel):
    venue: str
    market: str
    side: str
    size: float
    price: float | None = None


class JupiterQuoteRequest(BaseModel):
    input_mint: str
    output_mint: str
    amount: int
    slippage_bps: int = 50


class JupiterSwapRequest(BaseModel):
    quote_response: dict


@router.post("/order")
def place_order(req: OrderRequest):
    try:
        side = req.side.lower().strip()
        if side not in ("buy", "sell"):
            raise HTTPException(
                status_code=400,
                detail={"status": "error", "message": f"Invalid side '{req.side}' — must be 'buy' or 'sell'"},
            )

        result = _exec_router.route_order(
            venue=req.venue,
            market=req.market,
            side=side,
            size=req.size,
            price=req.price,
        )
        if result.get("status") == "blocked":
            raise HTTPException(status_code=403, detail=result)

        fill_price = req.price or result.get("fill_price", 0.0)

        _positions_repo.save_paper_trade(
            venue=req.venue,
            market=req.market,
            side=side,
            size=req.size,
            price=fill_price,
            order_type="limit",
            status=result.get("status", "unknown"),
        )

        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error placing order: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail={"status": "error", "message": "Failed to place order"})


@router.get("/positions")
def get_positions():
    try:
        positions = _exec_router.get_all_positions()
        db_positions = _positions_repo.get_all()
        return {
            "live_positions": positions,
            "db_positions": db_positions,
        }
    except Exception as exc:
        logger.error("Error fetching positions: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch positions")


@router.get("/paper-trades")
def get_paper_trades():
    try:
        trades = _positions_repo.get_paper_trades(limit=50)
        return {"trades": trades, "count": len(trades)}
    except Exception as exc:
        logger.error("Error fetching paper trades: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch paper trades")


@router.post("/jupiter/quote")
def jupiter_quote(req: JupiterQuoteRequest):
    try:
        result = _jupiter.get_quote(
            input_mint=req.input_mint,
            output_mint=req.output_mint,
            amount=req.amount,
            slippage_bps=req.slippage_bps,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error getting Jupiter quote: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get Jupiter quote")


@router.post("/jupiter/swap")
def jupiter_swap(req: JupiterSwapRequest):
    try:
        build_result = _jupiter.build_swap(req.quote_response)
        if build_result.get("status") == "error":
            raise HTTPException(status_code=400, detail=build_result)

        swap_tx = build_result.get("swap_tx", {})
        exec_result = _jupiter.execute_swap(swap_tx)
        if exec_result.get("status") == "error":
            raise HTTPException(status_code=400, detail=exec_result)

        return exec_result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error executing Jupiter swap: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to execute Jupiter swap")
