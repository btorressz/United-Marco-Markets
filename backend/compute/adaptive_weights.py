import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    "macro": 0.25,
    "carry": 0.25,
    "microstructure": 0.25,
    "momentum": 0.25,
}

ADAPTIVE_WEIGHTS_ENABLED = os.environ.get("ADAPTIVE_WEIGHTS", "1") == "1"


def compute_weights(
    shock_score: float = 0.0,
    funding_skew: float = 0.0,
    vol_regime: str = "normal",
    tariff_index: float = 50.0,
) -> dict:
    if not ADAPTIVE_WEIGHTS_ENABLED:
        return {
            "weights": dict(DEFAULT_WEIGHTS),
            "regime_inputs": {
                "shock_score": shock_score,
                "funding_skew": funding_skew,
                "vol_regime": vol_regime,
                "tariff_index": tariff_index,
            },
            "adaptive_enabled": False,
            "adjustments": [],
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    weights = dict(DEFAULT_WEIGHTS)
    adjustments = []

    if shock_score > 70:
        bump = min((shock_score - 70) / 100, 0.15)
        weights["macro"] += bump
        adjustments.append(f"macro +{bump:.3f} (shock_score={shock_score:.1f})")
    elif shock_score > 50:
        bump = min((shock_score - 50) / 200, 0.07)
        weights["macro"] += bump
        adjustments.append(f"macro +{bump:.3f} (moderate shock={shock_score:.1f})")

    abs_skew = abs(funding_skew)
    if abs_skew > 0.05:
        bump = min(abs_skew * 1.0, 0.15)
        weights["carry"] += bump
        adjustments.append(f"carry +{bump:.3f} (funding_skew={funding_skew:.4f})")
    elif abs_skew > 0.02:
        bump = min(abs_skew * 0.5, 0.07)
        weights["carry"] += bump
        adjustments.append(f"carry +{bump:.3f} (moderate skew={funding_skew:.4f})")

    if vol_regime == "high":
        bump = 0.10
        weights["microstructure"] += bump
        adjustments.append(f"microstructure +{bump:.3f} (vol_regime=high)")
    elif vol_regime == "extreme":
        bump = 0.15
        weights["microstructure"] += bump
        adjustments.append(f"microstructure +{bump:.3f} (vol_regime=extreme)")

    if tariff_index > 75:
        bump = min((tariff_index - 75) / 200, 0.10)
        weights["macro"] += bump
        weights["momentum"] += bump * 0.5
        adjustments.append(f"macro +{bump:.3f}, momentum +{bump * 0.5:.3f} (tariff_index={tariff_index:.1f})")

    total = sum(weights.values())
    if total > 0:
        weights = {k: round(v / total, 4) for k, v in weights.items()}

    return {
        "weights": weights,
        "regime_inputs": {
            "shock_score": shock_score,
            "funding_skew": funding_skew,
            "vol_regime": vol_regime,
            "tariff_index": tariff_index,
        },
        "adaptive_enabled": True,
        "adjustments": adjustments,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
