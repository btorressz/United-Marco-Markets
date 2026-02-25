import time
import logging
from collections import deque

logger = logging.getLogger(__name__)

_basis_history: deque = deque(maxlen=200)


def compute_basis(
    hl_perp_price: float,
    drift_perp_price: float,
    spot_price: float,
    hl_funding: float = 0.0,
    drift_funding: float = 0.0,
) -> dict:
    now = time.time()

    if spot_price <= 0:
        return _empty_basis(now)

    hl_spot_basis_bps = ((hl_perp_price - spot_price) / spot_price) * 10_000
    drift_spot_basis_bps = ((drift_perp_price - spot_price) / spot_price) * 10_000

    hl_drift_spread_bps = 0.0
    if drift_perp_price > 0:
        hl_drift_spread_bps = ((hl_perp_price - drift_perp_price) / drift_perp_price) * 10_000

    avg_basis_bps = (hl_spot_basis_bps + drift_spot_basis_bps) / 2.0

    annualized_basis_bps = avg_basis_bps * 365 * 3

    funding_diff = hl_funding - drift_funding
    funding_diff_bps = funding_diff * 10_000

    net_carry = annualized_basis_bps + funding_diff_bps

    entry = {
        "ts": now,
        "hl_spot_basis_bps": round(hl_spot_basis_bps, 2),
        "drift_spot_basis_bps": round(drift_spot_basis_bps, 2),
        "hl_drift_spread_bps": round(hl_drift_spread_bps, 2),
        "annualized_basis_bps": round(annualized_basis_bps, 2),
        "funding_diff_bps": round(funding_diff_bps, 2),
        "net_carry": round(net_carry, 2),
        "hl_perp_price": hl_perp_price,
        "drift_perp_price": drift_perp_price,
        "spot_price": spot_price,
        "hl_funding": hl_funding,
        "drift_funding": drift_funding,
    }

    _basis_history.append(entry)

    return entry


def assess_feasibility(
    spread_bps: float,
    liquidity_depth: float = 1.0,
    integrity_status: str = "ok",
) -> int:
    score = 100

    abs_spread = abs(spread_bps)
    if abs_spread > 100:
        score -= 40
    elif abs_spread > 50:
        score -= 20
    elif abs_spread > 20:
        score -= 10

    if liquidity_depth < 0.3:
        score -= 30
    elif liquidity_depth < 0.6:
        score -= 15
    elif liquidity_depth < 0.8:
        score -= 5

    if integrity_status != "ok":
        score -= 25

    return max(0, min(100, score))


def get_history(limit: int = 50) -> list[dict]:
    items = list(_basis_history)[-limit:]
    items.reverse()
    return items


def _empty_basis(ts: float) -> dict:
    return {
        "ts": ts,
        "hl_spot_basis_bps": 0.0,
        "drift_spot_basis_bps": 0.0,
        "hl_drift_spread_bps": 0.0,
        "annualized_basis_bps": 0.0,
        "funding_diff_bps": 0.0,
        "net_carry": 0.0,
        "hl_perp_price": 0.0,
        "drift_perp_price": 0.0,
        "spot_price": 0.0,
        "hl_funding": 0.0,
        "drift_funding": 0.0,
        "error": "invalid_spot_price",
    }
