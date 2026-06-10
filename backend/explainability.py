import logging
from datetime import datetime, timezone
from typing import Any

from backend.ml.feature_store import FEATURE_NAMES, features_to_vector
from backend.ml.training import get_trained_model

logger = logging.getLogger(__name__)

_FEATURE_DESCRIPTIONS = {
    "tariff_index": "Global tariff pressure level (0-100)",
    "tariff_delta": "Rate of change of tariff index",
    "shock_score": "GDELT news shock z-score",
    "shock_abs": "Absolute shock magnitude",
    "funding_skew": "Funding rate direction and magnitude",
    "basis_spread": "Perpetual vs spot basis spread",
    "vol_regime_encoded": "Volatility regime (0=low, 1=extreme)",
    "stable_health": "Stablecoin peg health score",
    "stable_flow": "Stablecoin flow momentum",
    "divergence_score": "Cross-venue price divergence",
    "orderbook_imbalance": "Orderbook bid/ask imbalance",
    "liquidity_score": "Market liquidity quality score",
    "slippage_score": "Expected slippage level",
    "exec_quality": "Execution quality index",
    "predictor_conf": "Macro predictor confidence",
}

_FEATURE_DIRECTION = {
    "tariff_index": -1,
    "tariff_delta": -1,
    "shock_score": -1,
    "shock_abs": -1,
    "funding_skew": 1,
    "basis_spread": 1,
    "vol_regime_encoded": -1,
    "stable_health": 1,
    "stable_flow": 1,
    "divergence_score": -1,
    "orderbook_imbalance": 1,
    "liquidity_score": 1,
    "slippage_score": -1,
    "exec_quality": 1,
    "predictor_conf": 1,
}

_FEATURE_BASELINES = {
    "tariff_index": 30.0,
    "tariff_delta": 0.0,
    "shock_score": 0.0,
    "shock_abs": 0.0,
    "funding_skew": 0.0,
    "basis_spread": 0.0,
    "vol_regime_encoded": 0.25,
    "stable_health": 1.0,
    "stable_flow": 0.0,
    "divergence_score": 0.0,
    "orderbook_imbalance": 0.0,
    "liquidity_score": 0.8,
    "slippage_score": 0.1,
    "exec_quality": 0.8,
    "predictor_conf": 0.5,
}


def _try_shap(model_data: dict, features: dict[str, float]) -> list[dict[str, Any]] | None:
    try:
        import shap
        model = model_data["model"]
        scaler = model_data.get("scaler")
        vec = [features_to_vector(features)]
        if scaler is not None:
            vec = scaler.transform(vec)
        explainer = shap.LinearExplainer(model, vec)
        shap_vals = explainer.shap_values(vec)
        if hasattr(shap_vals, "__len__") and len(shap_vals) > 0:
            vals = shap_vals[0] if len(shap_vals[0]) == len(FEATURE_NAMES) else shap_vals
            contributions = []
            for i, name in enumerate(FEATURE_NAMES):
                val = float(vals[i]) if i < len(vals) else 0.0
                contributions.append({
                    "feature": name,
                    "contribution": round(val, 6),
                    "direction": "positive" if val > 0 else "negative",
                    "description": _FEATURE_DESCRIPTIONS.get(name, name),
                })
            contributions.sort(key=lambda x: abs(x["contribution"]), reverse=True)
            return contributions
    except Exception as exc:
        logger.debug("SHAP unavailable or failed: %s", exc)
    return None


def explain(features: dict[str, float]) -> dict[str, Any]:
    model_data = get_trained_model()

    shap_contribs = None
    if model_data is not None:
        shap_contribs = _try_shap(model_data, features)

    if shap_contribs is not None:
        contributions = shap_contribs
        method = "shap"
    else:
        contributions = _heuristic_contributions(features, model_data)
        method = "coefficient_proxy" if model_data else "heuristic"

    top_positive = [c for c in contributions if c["contribution"] > 0][:3]
    top_negative = [c for c in contributions if c["contribution"] < 0][:3]

    return {
        "contributions": contributions,
        "top_positive_drivers": top_positive,
        "top_negative_drivers": top_negative,
        "method": method,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _heuristic_contributions(
    features: dict[str, float],
    model_data: dict | None,
) -> list[dict[str, Any]]:
    if model_data is not None and model_data.get("type") == "sklearn_logistic":
        try:
            model = model_data["model"]
            coefs = model.coef_[0]
            scaler = model_data.get("scaler")
            vec = features_to_vector(features)
            if scaler is not None:
                vec_scaled = scaler.transform([vec])[0]
            else:
                vec_scaled = vec
            contributions = []
            for i, name in enumerate(FEATURE_NAMES):
                if i < len(coefs) and i < len(vec_scaled):
                    contrib = float(coefs[i] * vec_scaled[i])
                    contributions.append({
                        "feature": name,
                        "contribution": round(contrib, 6),
                        "direction": "positive" if contrib > 0 else "negative",
                        "description": _FEATURE_DESCRIPTIONS.get(name, name),
                    })
            contributions.sort(key=lambda x: abs(x["contribution"]), reverse=True)
            return contributions
        except Exception as exc:
            logger.debug("Coefficient proxy failed: %s", exc)

    contributions = []
    for name in FEATURE_NAMES:
        val = features.get(name, _FEATURE_BASELINES.get(name, 0.0))
        baseline = _FEATURE_BASELINES.get(name, 0.0)
        direction_sign = _FEATURE_DIRECTION.get(name, 1)
        delta = (val - baseline)
        norm = max(abs(baseline) + 1.0, 1.0)
        contrib = direction_sign * delta / norm * 0.1
        contributions.append({
            "feature": name,
            "contribution": round(contrib, 6),
            "direction": "positive" if contrib > 0 else "negative",
            "description": _FEATURE_DESCRIPTIONS.get(name, name),
        })
    contributions.sort(key=lambda x: abs(x["contribution"]), reverse=True)
    return contributions
