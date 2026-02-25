import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from backend.core.schemas import DivergenceResponse, AlertResponse
from backend.data.repositories.market_repo import MarketRepository
from backend.data.repositories.events_repo import EventsRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/divergence", tags=["divergence"])

_market_repo = MarketRepository()
_events_repo = EventsRepository()


@router.get("/spreads", response_model=list[DivergenceResponse])
def get_spreads():
    try:
        all_ticks = _market_repo.get_all_latest()
        by_symbol: dict[str, list[dict]] = {}
        for tick in all_ticks:
            sym = tick["symbol"]
            by_symbol.setdefault(sym, []).append(tick)

        spreads = []
        for sym, ticks in by_symbol.items():
            if len(ticks) < 2:
                continue
            for i in range(len(ticks)):
                for j in range(i + 1, len(ticks)):
                    a, b = ticks[i], ticks[j]
                    mid = (a["price"] + b["price"]) / 2.0
                    spread_bps = ((a["price"] - b["price"]) / mid * 10000) if mid else 0.0
                    spreads.append(DivergenceResponse(
                        market=sym,
                        venue_a=a["venue"],
                        venue_b=b["venue"],
                        price_a=a["price"],
                        price_b=b["price"],
                        spread_bps=round(spread_bps, 2),
                        ts=datetime.now(timezone.utc),
                    ))
        return spreads
    except Exception as exc:
        logger.error("Error computing spreads: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to compute spreads")


@router.get("/alerts", response_model=list[AlertResponse])
def get_alerts():
    try:
        events = _events_repo.get_by_type("DIVERGENCE_ALERT", limit=20)
        alerts = []
        for ev in events:
            payload = ev.get("payload", {})
            if isinstance(payload, str):
                import json
                payload = json.loads(payload)
            alerts.append(AlertResponse(
                alert_type=ev["event_type"],
                message=payload.get("message", f"Divergence alert from {ev['source']}"),
                severity="warning",
                payload=payload,
                ts=ev["ts"],
            ))
        return alerts
    except Exception as exc:
        logger.error("Error fetching divergence alerts: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch divergence alerts")
