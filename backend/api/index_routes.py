import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from backend.core.schemas import IndexLatestResponse, IndexHistoryResponse, IndexComponentsResponse, AlertResponse
from backend.core.timeutils import window_to_seconds
from backend.core.state_store import StateStore
from backend.data.repositories.index_repo import IndexRepository
from backend.data.repositories.events_repo import EventsRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/index", tags=["index"])

_index_repo = IndexRepository()
_events_repo = EventsRepository()
_store = StateStore()


@router.get("/latest", response_model=IndexLatestResponse)
def get_latest():
    try:
        row = _index_repo.get_latest()
        if not row:
            return IndexLatestResponse(
                tariff_index=0.0,
                shock_score=0.0,
                ts=datetime.now(timezone.utc),
                components={},
            )
        components = row.get("components", {})
        if isinstance(components, str):
            import json
            components = json.loads(components)
        return IndexLatestResponse(
            tariff_index=row["index_level"],
            shock_score=row["shock_score"],
            ts=row["ts"],
            components=components or {},
        )
    except Exception as exc:
        logger.error("Error fetching latest index: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch latest index")


@router.get("/history", response_model=IndexHistoryResponse)
def get_history(window: str = Query(default="7d")):
    try:
        seconds = window_to_seconds(window)
        rows = _index_repo.get_history(seconds)
        points = []
        for r in rows:
            entry = {
                "index_level": r["index_level"],
                "rate_of_change": r["rate_of_change"],
                "shock_score": r["shock_score"],
                "ts": r["ts"].isoformat() if isinstance(r["ts"], datetime) else str(r["ts"]),
            }
            points.append(entry)
        return IndexHistoryResponse(points=points, window=window, count=len(points))
    except Exception as exc:
        logger.error("Error fetching index history: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch index history")


@router.get("/components", response_model=IndexComponentsResponse)
def get_components():
    try:
        comps = _index_repo.get_components()
        comp_dict = {c["name"]: c["value"] for c in comps}
        return IndexComponentsResponse(
            wits_weight=comp_dict.get("wits_weight", 0.0),
            gdelt_weight=comp_dict.get("gdelt_weight", 0.0),
            funding_weight=comp_dict.get("funding_weight", 0.0),
            components=comp_dict,
        )
    except Exception as exc:
        logger.error("Error fetching index components: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch index components")


@router.get("/alerts", response_model=list[AlertResponse])
def get_alerts():
    try:
        index_events = _events_repo.get_by_type("INDEX_UPDATE", limit=10)
        shock_events = _events_repo.get_by_type("SHOCK_SPIKE", limit=10)
        all_events = index_events + shock_events
        all_events.sort(key=lambda e: e.get("ts", ""), reverse=True)
        alerts = []
        for ev in all_events[:20]:
            payload = ev.get("payload", {})
            if isinstance(payload, str):
                import json
                payload = json.loads(payload)
            severity = "warning" if ev["event_type"] == "SHOCK_SPIKE" else "info"
            alerts.append(AlertResponse(
                alert_type=ev["event_type"],
                message=payload.get("message", f"{ev['event_type']} from {ev['source']}"),
                severity=severity,
                payload=payload,
                ts=ev["ts"],
            ))
        return alerts
    except Exception as exc:
        logger.error("Error fetching index alerts: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch index alerts")


@router.get("/macro-terminal")
def get_macro_terminal():
    now = datetime.now(timezone.utc)
    result = {
        "tariff_series": [],
        "rolling_delta": [],
        "country_weights": [],
        "correlations": {},
        "ts": now.isoformat(),
    }

    try:
        history_rows = _index_repo.get_history(86400 * 30)
        if history_rows:
            for r in history_rows:
                ts_str = r["ts"].isoformat() if isinstance(r["ts"], datetime) else str(r["ts"])
                result["tariff_series"].append({
                    "index_level": r["index_level"],
                    "ts": ts_str,
                })

            for i in range(1, len(history_rows)):
                prev = history_rows[i - 1]["index_level"]
                curr = history_rows[i]["index_level"]
                delta = curr - prev
                ts_str = history_rows[i]["ts"].isoformat() if isinstance(history_rows[i]["ts"], datetime) else str(history_rows[i]["ts"])
                result["rolling_delta"].append({
                    "delta": round(delta, 4),
                    "ts": ts_str,
                })
    except Exception:
        logger.debug("Failed to load tariff series", exc_info=True)

    from backend.config import WITS_COUNTRIES
    country_names = {"156": "China", "276": "EU", "USA": "USA", "CHN": "China", "EU": "EU"}
    country_wts = []
    for c in WITS_COUNTRIES:
        snap = _store.get_snapshot(f"wits:tariff:840:{c}:TOTAL")
        weight = 0.0
        tariff = 0.0
        if snap and snap.get("records"):
            recs = snap["records"]
            if recs:
                tariff = recs[0].get("tariff_rate", 0) if isinstance(recs[0], dict) else 0
                trade_val = recs[0].get("trade_value", 100000) if isinstance(recs[0], dict) else 100000
                weight = trade_val
        country_wts.append({
            "country": country_names.get(c, c),
            "code": c,
            "tariff_rate": tariff,
            "trade_weight": weight,
        })

    total_weight = sum(cw["trade_weight"] for cw in country_wts) or 1
    for cw in country_wts:
        cw["weight_pct"] = round(cw["trade_weight"] / total_weight * 100, 2)
    result["country_weights"] = country_wts

    try:
        history_rows = _index_repo.get_history(86400 * 7)
        if history_rows and len(history_rows) >= 3:
            deltas = []
            for i in range(1, len(history_rows)):
                deltas.append(history_rows[i]["index_level"] - history_rows[i - 1]["index_level"])

            shock_scores = [r.get("shock_score", 0) for r in history_rows[1:]]

            n = min(len(deltas), len(shock_scores))
            if n >= 2:
                mean_d = sum(deltas[:n]) / n
                mean_s = sum(shock_scores[:n]) / n
                cov = sum((deltas[i] - mean_d) * (shock_scores[i] - mean_s) for i in range(n)) / n
                var_d = sum((d - mean_d) ** 2 for d in deltas[:n]) / n
                var_s = sum((s - mean_s) ** 2 for s in shock_scores[:n]) / n
                denom = (var_d ** 0.5) * (var_s ** 0.5)
                corr_shock = round(cov / denom, 4) if denom > 1e-10 else 0.0
            else:
                corr_shock = 0.0

            result["correlations"] = {
                "tariff_delta_vs_shock": corr_shock,
                "tariff_delta_vs_btc_returns": 0.0,
                "tariff_delta_vs_funding": 0.0,
                "tariff_delta_vs_volatility": 0.0,
            }
    except Exception:
        logger.debug("Failed to compute correlations", exc_info=True)

    return result
