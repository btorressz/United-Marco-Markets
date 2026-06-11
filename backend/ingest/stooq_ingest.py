"""Simple fail-open Stooq fallback for EOD equity data."""
from __future__ import annotations

import csv
import urllib.request
from datetime import datetime, timezone
from typing import Any

from backend.ingest.yfinance_ingest import demo_history


def fetch_history(ticker: str) -> dict[str, Any]:
    symbol = ticker.lower().replace(".", "-") + ".us"
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    try:
        with urllib.request.urlopen(url, timeout=4) as resp:  # nosec - public CSV endpoint, fail-open
            text = resp.read().decode("utf-8", errors="ignore")
        rows = []
        for row in csv.DictReader(text.splitlines()):
            close = float(row.get("Close") or 0)
            if close <= 0:
                continue
            ts = datetime.fromisoformat(row["Date"]).replace(tzinfo=timezone.utc).isoformat()
            rows.append({"ts": ts, "open": float(row.get("Open") or close), "high": float(row.get("High") or close), "low": float(row.get("Low") or close), "close": close, "volume": int(float(row.get("Volume") or 0))})
        if rows:
            return {"ticker": ticker.upper(), "history": rows[-365:], "provider_status": {"name": "Stooq", "status": "ok", "ts": datetime.now(timezone.utc).isoformat()}, "degraded": False}
        raise RuntimeError("empty Stooq response")
    except Exception as exc:
        return {"ticker": ticker.upper(), "history": demo_history(ticker), "provider_status": {"name": "Stooq", "status": "degraded", "message": f"demo fallback: {exc}", "ts": datetime.now(timezone.utc).isoformat()}, "degraded": True}
