import logging
import math
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

SIZE_BUCKETS = [100, 500, 1000, 5000, 10000, 50000, 100000]
SLIPPAGE_THRESHOLDS_BPS = [10, 25, 50]


def estimate_slippage_curve(
    ob_depth: float = 0,
    spread_bps: float = 5.0,
    volatility: float = 0.03,
    recent_slippage_bps: float = 0,
    venue: str = "unknown",
) -> dict[str, Any]:
    curve = []
    depth = max(ob_depth, 1000.0)

    base_slip = max(spread_bps * 0.5, 0.5)

    if recent_slippage_bps > 0:
        base_slip = (base_slip + recent_slippage_bps) / 2.0

    vol_multiplier = 1.0 + volatility * 10.0

    for size in SIZE_BUCKETS:
        depth_ratio = size / depth
        impact_bps = base_slip + depth_ratio * 50.0 * vol_multiplier
        impact_bps = round(impact_bps, 2)
        curve.append({
            "size_usd": size,
            "expected_slippage_bps": impact_bps,
        })

    return {
        "venue": venue,
        "curve": curve,
        "inputs": {
            "ob_depth": ob_depth,
            "spread_bps": spread_bps,
            "volatility": volatility,
            "recent_slippage_bps": recent_slippage_bps,
        },
        "data_quality": _compute_data_quality(ob_depth, spread_bps, recent_slippage_bps),
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def compute_max_safe_sizes(
    ob_depth: float = 0,
    spread_bps: float = 5.0,
    volatility: float = 0.03,
    recent_slippage_bps: float = 0,
    venue: str = "unknown",
) -> dict[str, Any]:
    curve_data = estimate_slippage_curve(ob_depth, spread_bps, volatility, recent_slippage_bps, venue)
    curve = curve_data["curve"]

    safe_sizes = {}
    for threshold in SLIPPAGE_THRESHOLDS_BPS:
        max_size = 0
        for point in curve:
            if point["expected_slippage_bps"] <= threshold:
                max_size = point["size_usd"]
            else:
                break
        safe_sizes[f"{threshold}bps"] = max_size

    notes = []
    if ob_depth == 0:
        notes.append("No orderbook depth data — estimates based on spread only")
    if recent_slippage_bps == 0:
        notes.append("No recent slippage data — using model estimates only")
    if volatility > 0.05:
        notes.append("High volatility environment — actual slippage may exceed estimates")

    return {
        "venue": venue,
        "max_safe_sizes": safe_sizes,
        "thresholds_bps": SLIPPAGE_THRESHOLDS_BPS,
        "slippage_curve": curve,
        "data_quality": curve_data["data_quality"],
        "notes": notes,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _compute_data_quality(ob_depth: float, spread_bps: float, recent_slippage: float) -> dict:
    score = 30
    sources = 0

    if ob_depth > 0:
        score += 30
        sources += 1
    if spread_bps > 0:
        score += 20
        sources += 1
    if recent_slippage > 0:
        score += 20
        sources += 1

    quality = "good" if score >= 70 else "fair" if score >= 50 else "sparse"

    return {
        "score": score,
        "quality": quality,
        "data_sources_used": sources,
    }


def get_multi_venue_slippage(venue_data: dict[str, dict]) -> dict[str, Any]:
    results = {}
    for venue, params in venue_data.items():
        try:
            results[venue] = compute_max_safe_sizes(
                ob_depth=params.get("ob_depth", 0),
                spread_bps=params.get("spread_bps", 5.0),
                volatility=params.get("volatility", 0.03),
                recent_slippage_bps=params.get("recent_slippage_bps", 0),
                venue=venue,
            )
        except Exception:
            logger.debug("Slippage model failed for venue %s", venue, exc_info=True)
            results[venue] = {"venue": venue, "error": "computation_failed"}

    return {
        "venues": results,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
