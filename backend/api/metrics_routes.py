import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from backend.compute.execution_metrics import get_execution_metrics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/metrics", tags=["metrics"])

_metrics = get_execution_metrics()


@router.get("/eqi")
def get_eqi():
    try:
        return _metrics.get_eqi()
    except Exception as exc:
        logger.error("Error fetching EQI: %s", exc, exc_info=True)
        return {
            "eqi_score": 0,
            "latency_p50_ms": 0,
            "latency_p95_ms": 0,
            "slippage_mean_bps": 0,
            "anomalies": [],
            "venue_breakdown": {},
            "total_fills": 0,
            "ts": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/anomalies")
def get_anomalies():
    try:
        eqi = _metrics.get_eqi()
        return {"anomalies": eqi.get("anomalies", []), "ts": datetime.now(timezone.utc).isoformat()}
    except Exception:
        return {"anomalies": [], "ts": datetime.now(timezone.utc).isoformat()}
