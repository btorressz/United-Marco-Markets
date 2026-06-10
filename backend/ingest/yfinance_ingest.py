"""Fail-open yfinance equity ingestion helpers.

The app must run without API keys and without yfinance installed.  These helpers
therefore treat yfinance as an optional MVP research provider and always return
safe demo data with degraded provider status when anything goes wrong.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

EQUITY_INDEX_ETFS = ["SPY", "QQQ", "DIA", "IWM"]
SECTOR_ETFS = ["XLI", "XLY", "XLP", "XLK", "XLE", "XLF", "XLB", "XLV", "SMH", "SOXX", "ITA", "XRT", "KWEB", "FXI", "EEM"]
TARIFF_SENSITIVE = ["AAPL", "TSLA", "NVDA", "AMD", "INTC", "MSFT", "AMZN", "NKE", "LULU", "WMT", "TGT", "COST", "HD", "CAT", "DE", "BA", "F", "GM", "XOM", "CVX", "FCX", "NUE", "STLD"]
EQUITY_UNIVERSE = EQUITY_INDEX_ETFS + SECTOR_ETFS + TARIFF_SENSITIVE

SECTORS = {
    "SPY": "Broad Market", "QQQ": "Growth/Technology", "DIA": "Large Cap", "IWM": "Small Cap",
    "XLI": "Industrials", "XLY": "Consumer Discretionary", "XLP": "Consumer Staples", "XLK": "Technology",
    "XLE": "Energy", "XLF": "Financials", "XLB": "Materials", "XLV": "Health Care", "SMH": "Semiconductors",
    "SOXX": "Semiconductors", "ITA": "Aerospace/Defense", "XRT": "Retail", "KWEB": "China Internet",
    "FXI": "China Large Cap", "EEM": "Emerging Markets", "AAPL": "Technology", "TSLA": "Autos",
    "NVDA": "Semiconductors", "AMD": "Semiconductors", "INTC": "Semiconductors", "MSFT": "Technology",
    "AMZN": "Retail/Cloud", "NKE": "Apparel", "LULU": "Apparel", "WMT": "Retail", "TGT": "Retail",
    "COST": "Retail", "HD": "Retail", "CAT": "Machinery", "DE": "Machinery", "BA": "Aerospace",
    "F": "Autos", "GM": "Autos", "XOM": "Energy", "CVX": "Energy", "FCX": "Materials",
    "NUE": "Steel", "STLD": "Steel",
}

_BASE_PRICES = {ticker: 80.0 + i * 7.5 for i, ticker in enumerate(EQUITY_UNIVERSE)} | {
    "SPY": 540.0, "QQQ": 460.0, "DIA": 390.0, "IWM": 205.0, "AAPL": 195.0,
    "TSLA": 185.0, "NVDA": 120.0, "AMD": 160.0, "MSFT": 430.0, "AMZN": 185.0,
}


def _provider(name: str, status: str, message: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "message": message,
        "research_grade": name == "yfinance",
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def demo_history(ticker: str, days: int = 90) -> list[dict[str, Any]]:
    ticker = ticker.upper()
    days = max(5, min(int(days or 90), 365))
    base = float(_BASE_PRICES.get(ticker, 100.0))
    seed = sum(ord(c) for c in ticker) % 17
    rows: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).replace(hour=21, minute=0, second=0, microsecond=0)
    price = base
    for i in range(days):
        d = now - timedelta(days=days - i - 1)
        drift = 0.0005 + (seed - 8) * 0.00008
        cyc = math.sin((i + seed) / 5.0) * 0.006
        shock = -0.012 if ticker in {"AAPL", "TSLA", "NKE", "CAT", "DE", "BA", "F", "GM", "FCX", "NUE", "STLD"} and i > days - 18 else 0.0
        ret = drift + cyc + shock / max(1, days - i)
        open_p = price
        close = max(1.0, open_p * (1.0 + ret))
        high = max(open_p, close) * (1.0 + 0.004 + (seed % 3) * 0.001)
        low = min(open_p, close) * (1.0 - 0.004 - (seed % 4) * 0.001)
        volume = int(1_000_000 + seed * 125_000 + (1 + abs(cyc) * 50) * 120_000)
        rows.append({"ts": d.isoformat(), "open": round(open_p, 4), "high": round(high, 4), "low": round(low, 4), "close": round(close, 4), "volume": volume})
        price = close
    return rows


def fetch_history(ticker: str, period: str = "3mo", interval: str = "1d") -> dict[str, Any]:
    ticker = ticker.upper().strip()
    try:
        import yfinance as yf  # type: ignore
        hist = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
        rows: list[dict[str, Any]] = []
        if hist is not None and not hist.empty:
            for idx, row in hist.tail(365).iterrows():
                ts = idx.to_pydatetime().astimezone(timezone.utc).isoformat() if hasattr(idx, "to_pydatetime") else datetime.now(timezone.utc).isoformat()
                close = float(row.get("Close", 0) or 0)
                if close <= 0:
                    continue
                rows.append({
                    "ts": ts,
                    "open": float(row.get("Open", close) or close),
                    "high": float(row.get("High", close) or close),
                    "low": float(row.get("Low", close) or close),
                    "close": close,
                    "volume": int(row.get("Volume", 0) or 0),
                })
        if rows:
            return {"ticker": ticker, "history": rows, "provider_status": _provider("yfinance", "ok", "MVP research-grade provider"), "degraded": False}
        raise RuntimeError("empty yfinance response")
    except Exception as exc:
        rows = demo_history(ticker)
        return {"ticker": ticker, "history": rows, "provider_status": _provider("yfinance", "degraded", f"fallback demo data: {exc}"), "degraded": True}


def fetch_quote(ticker: str) -> dict[str, Any]:
    data = fetch_history(ticker, period="1mo")
    hist = data.get("history", [])
    last = hist[-1] if hist else demo_history(ticker, 5)[-1]
    prev = hist[-2] if len(hist) > 1 else last
    return {
        "ticker": ticker.upper(),
        "price": last["close"],
        "previous_close": prev["close"],
        "daily_return": ((last["close"] / prev["close"]) - 1.0) if prev.get("close") else 0.0,
        "volume": last.get("volume", 0),
        "sector": SECTORS.get(ticker.upper(), "Unknown"),
        "data_ts": last.get("ts"),
        "provider_status": data.get("provider_status"),
        "degraded": data.get("degraded", False),
    }
