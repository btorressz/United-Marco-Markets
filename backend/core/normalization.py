import logging
from datetime import datetime, timezone
from typing import Any

from backend.core.models import PriceTick, FundingTick

logger = logging.getLogger(__name__)


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _parse_ts(val: Any) -> datetime:
    if val is None:
        return datetime.now(timezone.utc)
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val
    if isinstance(val, (int, float)):
        ts = float(val)
        if ts > 1e12:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(val, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                dt = datetime.strptime(val, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
    return datetime.now(timezone.utc)


def normalize_hyperliquid_tick(data: dict[str, Any]) -> PriceTick:
    return PriceTick(
        symbol=str(data.get("coin", data.get("symbol", "UNKNOWN"))),
        venue="hyperliquid",
        price=_safe_float(data.get("markPx", data.get("price", 0))),
        ts=_parse_ts(data.get("ts", data.get("time"))),
        confidence=1.0,
    )


def normalize_hyperliquid_funding(data: dict[str, Any]) -> FundingTick:
    return FundingTick(
        venue="hyperliquid",
        market=str(data.get("coin", data.get("market", "UNKNOWN"))),
        funding_rate=_safe_float(data.get("fundingRate", data.get("funding_rate", 0))),
        ts=_parse_ts(data.get("ts", data.get("time"))),
    )


def normalize_drift_tick(data: dict[str, Any]) -> PriceTick:
    price_raw = _safe_float(data.get("price", data.get("oraclePrice", 0)))
    if data.get("price_scale"):
        price_raw = price_raw / _safe_float(data["price_scale"], 1)
    return PriceTick(
        symbol=str(data.get("symbol", data.get("marketName", "UNKNOWN"))),
        venue="drift",
        price=price_raw,
        ts=_parse_ts(data.get("ts", data.get("slot"))),
        confidence=_safe_float(data.get("confidence", 0.9), 0.9),
    )


def normalize_drift_funding(data: dict[str, Any]) -> FundingTick:
    rate = _safe_float(data.get("fundingRate", data.get("funding_rate", 0)))
    if data.get("rate_scale"):
        rate = rate / _safe_float(data["rate_scale"], 1)
    return FundingTick(
        venue="drift",
        market=str(data.get("marketName", data.get("market", "UNKNOWN"))),
        funding_rate=rate,
        ts=_parse_ts(data.get("ts", data.get("slot"))),
    )


def normalize_pyth_tick(data: dict[str, Any]) -> PriceTick:
    price_obj = data.get("price", {})
    if isinstance(price_obj, dict):
        price_val = _safe_float(price_obj.get("price", 0))
        expo = _safe_float(price_obj.get("expo", 0))
        conf = _safe_float(price_obj.get("conf", 0))
        if expo != 0:
            price_val = price_val * (10 ** expo)
            conf = conf * (10 ** expo)
        confidence = max(0.0, min(1.0, 1.0 - (conf / max(price_val, 1e-9))))
    else:
        price_val = _safe_float(price_obj)
        confidence = _safe_float(data.get("confidence", 0.95), 0.95)

    return PriceTick(
        symbol=str(data.get("symbol", data.get("id", "UNKNOWN"))),
        venue="pyth",
        price=price_val,
        ts=_parse_ts(data.get("timestamp", data.get("publish_time"))),
        confidence=confidence,
    )


def normalize_kraken_tick(data: dict[str, Any]) -> PriceTick:
    if isinstance(data.get("result"), dict):
        for pair, info in data["result"].items():
            if isinstance(info, dict) and "c" in info:
                return PriceTick(
                    symbol=pair,
                    venue="kraken",
                    price=_safe_float(info["c"][0] if isinstance(info["c"], list) else info["c"]),
                    ts=_parse_ts(data.get("ts")),
                    confidence=1.0,
                )
    price = _safe_float(data.get("price", data.get("c", [0])))
    if isinstance(data.get("c"), list) and data["c"]:
        price = _safe_float(data["c"][0])

    return PriceTick(
        symbol=str(data.get("pair", data.get("symbol", "UNKNOWN"))),
        venue="kraken",
        price=price,
        ts=_parse_ts(data.get("ts", data.get("time"))),
        confidence=1.0,
    )


def normalize_coingecko_tick(data: dict[str, Any]) -> PriceTick:
    symbol = str(data.get("symbol", data.get("id", "UNKNOWN"))).upper()
    market_data = data.get("market_data", {})
    if market_data:
        price = _safe_float(market_data.get("current_price", {}).get("usd", 0))
    else:
        price = _safe_float(data.get("current_price", data.get("price", 0)))

    return PriceTick(
        symbol=symbol,
        venue="coingecko",
        price=price,
        ts=_parse_ts(data.get("last_updated", data.get("ts"))),
        confidence=0.85,
    )
