import time
import logging
from collections import deque

logger = logging.getLogger(__name__)

MAX_HISTORY = 100
PERSISTENCE_THRESHOLD_MINUTES = 5.0
SPREAD_THRESHOLD_BPS = 5.0


class FundingArbDetector:

    def __init__(self):
        self._history: deque = deque(maxlen=MAX_HISTORY)

    def detect_arb(self, hl_funding: float, drift_funding: float,
                   hl_ts: float | None = None, drift_ts: float | None = None) -> dict:
        now = time.time()
        hl_ts = hl_ts or now
        drift_ts = drift_ts or now

        spread_bps = (hl_funding - drift_funding) * 10000.0

        entry = {
            "hl_funding": hl_funding,
            "drift_funding": drift_funding,
            "spread_bps": spread_bps,
            "hl_ts": hl_ts,
            "drift_ts": drift_ts,
            "recorded_at": now,
        }
        self._history.append(entry)

        if abs(spread_bps) < SPREAD_THRESHOLD_BPS:
            return {
                "arb_signal": "none",
                "spread_bps": round(spread_bps, 2),
                "persistence_minutes": 0.0,
                "expected_net_carry": 0.0,
                "direction": None,
                "confidence": 0.0,
                "history_len": len(self._history),
            }

        if spread_bps > 0:
            direction = "short_hl_long_drift"
        else:
            direction = "long_hl_short_drift"

        persistence_minutes = self._compute_persistence(direction)

        expected_net_carry = self._compute_carry(spread_bps)

        historical_mean = self._historical_mean_spread()

        confidence = min(0.95, 0.5 + (persistence_minutes / 60.0) * 0.3 + (abs(spread_bps) / 50.0) * 0.2)

        return {
            "arb_signal": direction,
            "spread_bps": round(spread_bps, 2),
            "persistence_minutes": round(persistence_minutes, 2),
            "expected_net_carry": round(expected_net_carry, 4),
            "direction": direction,
            "confidence": round(confidence, 4),
            "historical_mean_spread_bps": round(historical_mean, 2),
            "history_len": len(self._history),
        }

    def _compute_persistence(self, current_direction: str) -> float:
        if len(self._history) < 2:
            return 0.0

        earliest_consistent = self._history[-1]["recorded_at"]
        for entry in reversed(self._history):
            if current_direction == "short_hl_long_drift" and entry["spread_bps"] > 0:
                earliest_consistent = entry["recorded_at"]
            elif current_direction == "long_hl_short_drift" and entry["spread_bps"] < 0:
                earliest_consistent = entry["recorded_at"]
            else:
                break

        return (self._history[-1]["recorded_at"] - earliest_consistent) / 60.0

    def _compute_carry(self, spread_bps: float) -> float:
        annualized = abs(spread_bps) * 3 * 365 / 10000.0
        return annualized

    def _historical_mean_spread(self) -> float:
        if not self._history:
            return 0.0
        return sum(e["spread_bps"] for e in self._history) / len(self._history)

    def get_history(self) -> list[dict]:
        return list(self._history)


_detector = FundingArbDetector()


def detect_arb(hl_funding: float, drift_funding: float,
               hl_ts: float | None = None, drift_ts: float | None = None) -> dict:
    return _detector.detect_arb(hl_funding, drift_funding, hl_ts, drift_ts)


def get_history() -> list[dict]:
    return _detector.get_history()
