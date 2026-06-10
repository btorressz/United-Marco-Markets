from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class EquityRiskAgent:
    name = "equity_risk_agent"

    def evaluate(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        signals = []
        now = datetime.now(timezone.utc).isoformat()
        for r in rows:
            ticker = r.get("ticker", "--")
            if float(r.get("volume_vs_avg", 1.0)) >= 1.5:
                signals.append(self._signal(ticker, "EQUITY_UNUSUAL_VOLUME", 0.72, "medium", "neutral", "review_size", "Volume is elevated versus 20-day average", now, r.get("data_ts")))
            if float(r.get("relative_strength_vs_spy", 0.0)) <= -0.03:
                signals.append(self._signal(ticker, "EQUITY_RELATIVE_WEAKNESS", 0.76, "medium", "bearish", "reduce_or_hedge", "Ticker is underperforming SPY over the recent window", now, r.get("data_ts")))
            if float(r.get("realized_volatility", 0.0)) >= 0.55:
                signals.append(self._signal(ticker, "CROSS_ASSET_RISK_OFF", 0.68, "medium", "bearish", "tighten_risk", "Realized equity volatility is elevated", now, r.get("data_ts")))
        return signals

    def _signal(self, ticker: str, signal: str, confidence: float, severity: str, direction: str, proposed_action: str, reason: str, ts: str, data_ts: str | None) -> dict[str, Any]:
        return {"agent": self.name, "ticker": ticker, "signal": signal, "confidence": confidence, "severity": severity, "direction": direction, "proposed_action": proposed_action, "reason": reason, "ts": ts, "data_ts_used": data_ts}
