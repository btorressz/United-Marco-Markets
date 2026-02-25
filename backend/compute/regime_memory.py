import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class RegimeMemory:

    def __init__(self):
        self._history: list[dict] = []
        self._max_entries = 500

    def record(
        self,
        shock_state: str,
        funding_regime: str,
        vol_regime: str,
        tariff_index: float,
        price: float,
    ) -> None:
        entry = {
            "shock_state": shock_state,
            "funding_regime": funding_regime,
            "vol_regime": vol_regime,
            "tariff_index": tariff_index,
            "price": price,
            "ts": datetime.now(timezone.utc).isoformat(),
            "return_4h": None,
            "return_24h": None,
            "return_3d": None,
        }
        self._history.append(entry)
        if len(self._history) > self._max_entries:
            self._history = self._history[-self._max_entries:]

    def update_returns(self, index: int, return_4h: float | None = None, return_24h: float | None = None, return_3d: float | None = None) -> None:
        if 0 <= index < len(self._history):
            if return_4h is not None:
                self._history[index]["return_4h"] = return_4h
            if return_24h is not None:
                self._history[index]["return_24h"] = return_24h
            if return_3d is not None:
                self._history[index]["return_3d"] = return_3d

    def find_analogues(
        self,
        shock_state: str,
        funding_regime: str,
        vol_regime: str,
        max_results: int = 10,
    ) -> list[dict]:
        matches = []
        for entry in self._history:
            score = 0
            if entry["shock_state"] == shock_state:
                score += 3
            if entry["funding_regime"] == funding_regime:
                score += 2
            if entry["vol_regime"] == vol_regime:
                score += 1
            if score >= 3 and entry.get("return_4h") is not None:
                matches.append({**entry, "match_score": score})

        matches.sort(key=lambda x: x["match_score"], reverse=True)
        return matches[:max_results]

    def get_outcome_distribution(
        self,
        shock_state: str,
        funding_regime: str,
        vol_regime: str,
    ) -> dict:
        matches = []
        for entry in self._history:
            score = 0
            if entry["shock_state"] == shock_state:
                score += 3
            if entry["funding_regime"] == funding_regime:
                score += 2
            if entry["vol_regime"] == vol_regime:
                score += 1
            if score >= 3:
                matches.append({**entry, "match_score": score})

        if not matches:
            return {
                "avg_return_4h": 0.0,
                "avg_return_24h": 0.0,
                "avg_return_3d": 0.0,
                "win_rate_4h": 0.0,
                "win_rate_24h": 0.0,
                "count": 0,
                "best_analog": None,
                "ts": datetime.now(timezone.utc).isoformat(),
            }

        returns_4h = [e["return_4h"] for e in matches if e.get("return_4h") is not None]
        returns_24h = [e["return_24h"] for e in matches if e.get("return_24h") is not None]
        returns_3d = [e["return_3d"] for e in matches if e.get("return_3d") is not None]

        avg_4h = sum(returns_4h) / len(returns_4h) if returns_4h else 0.0
        avg_24h = sum(returns_24h) / len(returns_24h) if returns_24h else 0.0
        avg_3d = sum(returns_3d) / len(returns_3d) if returns_3d else 0.0

        win_4h = sum(1 for r in returns_4h if r > 0) / len(returns_4h) if returns_4h else 0.0
        win_24h = sum(1 for r in returns_24h if r > 0) / len(returns_24h) if returns_24h else 0.0

        matches.sort(key=lambda x: x["match_score"], reverse=True)
        best_analog = matches[0] if matches else None

        return {
            "avg_return_4h": round(avg_4h, 6),
            "avg_return_24h": round(avg_24h, 6),
            "avg_return_3d": round(avg_3d, 6),
            "win_rate_4h": round(win_4h, 4),
            "win_rate_24h": round(win_24h, 4),
            "count": len(matches),
            "best_analog": best_analog,
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    def get_summary(self) -> dict:
        total = len(self._history)
        with_returns = sum(1 for e in self._history if e.get("return_4h") is not None)

        regime_counts = {}
        for e in self._history:
            key = f"{e['shock_state']}|{e['funding_regime']}|{e['vol_regime']}"
            regime_counts[key] = regime_counts.get(key, 0) + 1

        return {
            "total_records": total,
            "records_with_returns": with_returns,
            "regime_distribution": regime_counts,
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    def get_history(self, limit: int = 50) -> list[dict]:
        return self._history[-limit:]
