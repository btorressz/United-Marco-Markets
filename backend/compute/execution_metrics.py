import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

ROLLING_WINDOW = 100
SLIPPAGE_ANOMALY_THRESHOLD_BPS = 50.0
SLIPPAGE_ANOMALY_ZSCORE = 2.5


class ExecutionMetrics:

    def __init__(self, rolling_window: int = ROLLING_WINDOW):
        self._rolling_window = rolling_window
        self._fills: dict[str, deque] = defaultdict(lambda: deque(maxlen=self._rolling_window))
        self._all_fills: deque = deque(maxlen=self._rolling_window * 10)

    def record_fill(
        self,
        order_ts: float,
        fill_ts: float,
        expected_price: float,
        fill_price: float,
        venue: str,
        market: str,
    ) -> dict[str, Any]:
        latency_ms = max((fill_ts - order_ts) * 1000.0, 0.0)

        if expected_price > 0:
            slippage_bps = abs(fill_price - expected_price) / expected_price * 10000.0
        else:
            slippage_bps = 0.0

        signed_slippage_bps = 0.0
        if expected_price > 0:
            signed_slippage_bps = (fill_price - expected_price) / expected_price * 10000.0

        record = {
            "order_ts": order_ts,
            "fill_ts": fill_ts,
            "expected_price": expected_price,
            "fill_price": fill_price,
            "venue": venue,
            "market": market,
            "latency_ms": latency_ms,
            "slippage_bps": slippage_bps,
            "signed_slippage_bps": signed_slippage_bps,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

        self._fills[venue].append(record)
        self._all_fills.append(record)

        logger.debug(
            "Fill recorded: venue=%s market=%s latency=%.1fms slippage=%.2fbps",
            venue, market, latency_ms, slippage_bps,
        )

        return record

    def get_eqi(self) -> dict[str, Any]:
        all_records = list(self._all_fills)
        if not all_records:
            return {
                "eqi_score": 100.0,
                "fill_count": 0,
                "latency_p50_ms": 0.0,
                "latency_p95_ms": 0.0,
                "slippage_mean_bps": 0.0,
                "slippage_p50_bps": 0.0,
                "slippage_p95_bps": 0.0,
                "anomalies": [],
                "venue_breakdown": {},
                "ts": datetime.now(timezone.utc).isoformat(),
            }

        latencies = sorted(r["latency_ms"] for r in all_records)
        slippages = sorted(r["slippage_bps"] for r in all_records)

        lat_p50 = _percentile(latencies, 50)
        lat_p95 = _percentile(latencies, 95)
        slip_mean = sum(slippages) / len(slippages)
        slip_p50 = _percentile(slippages, 50)
        slip_p95 = _percentile(slippages, 95)

        latency_score = max(0.0, 100.0 - (lat_p95 / 10.0))
        slippage_score = max(0.0, 100.0 - (slip_p95 / 5.0))
        eqi = max(0.0, min(100.0, (latency_score * 0.4 + slippage_score * 0.6)))

        anomalies = []
        for r in all_records[-20:]:
            anomaly = self.detect_slippage_anomaly(r["slippage_bps"], r["venue"])
            if anomaly["is_anomaly"]:
                anomalies.append({
                    "venue": r["venue"],
                    "market": r["market"],
                    "slippage_bps": r["slippage_bps"],
                    "details": anomaly,
                })

        venue_breakdown = {}
        for venue, records in self._fills.items():
            recs = list(records)
            if not recs:
                continue
            v_lats = sorted(r["latency_ms"] for r in recs)
            v_slips = sorted(r["slippage_bps"] for r in recs)
            venue_breakdown[venue] = {
                "fill_count": len(recs),
                "latency_p50_ms": _percentile(v_lats, 50),
                "latency_p95_ms": _percentile(v_lats, 95),
                "slippage_mean_bps": sum(v_slips) / len(v_slips),
                "slippage_p95_bps": _percentile(v_slips, 95),
            }

        return {
            "eqi_score": round(eqi, 2),
            "fill_count": len(all_records),
            "latency_p50_ms": round(lat_p50, 2),
            "latency_p95_ms": round(lat_p95, 2),
            "slippage_mean_bps": round(slip_mean, 2),
            "slippage_p50_bps": round(slip_p50, 2),
            "slippage_p95_bps": round(slip_p95, 2),
            "anomalies": anomalies,
            "venue_breakdown": venue_breakdown,
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    def detect_slippage_anomaly(self, slippage_bps: float, venue: str) -> dict[str, Any]:
        venue_records = list(self._fills.get(venue, []))

        if len(venue_records) < 5:
            is_anomaly = slippage_bps > SLIPPAGE_ANOMALY_THRESHOLD_BPS
            return {
                "is_anomaly": is_anomaly,
                "slippage_bps": round(slippage_bps, 2),
                "venue": venue,
                "method": "absolute_threshold",
                "threshold_bps": SLIPPAGE_ANOMALY_THRESHOLD_BPS,
                "reason": f"slippage {slippage_bps:.1f}bps exceeds threshold {SLIPPAGE_ANOMALY_THRESHOLD_BPS}bps" if is_anomaly else "within threshold",
            }

        historical = [r["slippage_bps"] for r in venue_records]
        mean_slip = sum(historical) / len(historical)
        variance = sum((x - mean_slip) ** 2 for x in historical) / len(historical)
        std_slip = variance ** 0.5

        if std_slip < 0.01:
            is_anomaly = slippage_bps > SLIPPAGE_ANOMALY_THRESHOLD_BPS
            return {
                "is_anomaly": is_anomaly,
                "slippage_bps": round(slippage_bps, 2),
                "venue": venue,
                "method": "absolute_threshold",
                "threshold_bps": SLIPPAGE_ANOMALY_THRESHOLD_BPS,
                "mean_bps": round(mean_slip, 2),
                "std_bps": round(std_slip, 2),
                "reason": f"low variance, absolute check: {slippage_bps:.1f}bps vs {SLIPPAGE_ANOMALY_THRESHOLD_BPS}bps" if is_anomaly else "within threshold",
            }

        z_score = (slippage_bps - mean_slip) / std_slip
        is_anomaly = z_score > SLIPPAGE_ANOMALY_ZSCORE or slippage_bps > SLIPPAGE_ANOMALY_THRESHOLD_BPS

        return {
            "is_anomaly": is_anomaly,
            "slippage_bps": round(slippage_bps, 2),
            "venue": venue,
            "method": "z_score",
            "z_score": round(z_score, 2),
            "z_threshold": SLIPPAGE_ANOMALY_ZSCORE,
            "mean_bps": round(mean_slip, 2),
            "std_bps": round(std_slip, 2),
            "reason": f"z_score={z_score:.2f} exceeds {SLIPPAGE_ANOMALY_ZSCORE}" if is_anomaly else "within normal range",
        }


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f = int(k)
    c = f + 1
    if c >= len(sorted_values):
        return sorted_values[-1]
    d = k - f
    return sorted_values[f] + d * (sorted_values[c] - sorted_values[f])


_instance: ExecutionMetrics | None = None


def get_execution_metrics() -> ExecutionMetrics:
    global _instance
    if _instance is None:
        _instance = ExecutionMetrics()
    return _instance
