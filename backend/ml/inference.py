import logging
from datetime import datetime, timezone
from typing import Any

from backend.ml.feature_store import features_to_vector, FEATURE_NAMES
from backend.ml.training import get_trained_model

logger = logging.getLogger(__name__)

_CACHED_PREDICTION: dict[str, Any] | None = None


def _heuristic_predict(features: dict[str, float]) -> dict[str, Any]:
    tariff_idx = features.get("tariff_index", 30.0)
    shock = features.get("shock_score", 0.0)
    vol_enc = features.get("vol_regime_encoded", 0.25)
    stable_health = features.get("stable_health", 1.0)
    predictor_conf = features.get("predictor_conf", 0.5)
    exec_quality = features.get("exec_quality", 0.8)

    score = 0.5
    score -= (tariff_idx - 30.0) / 200.0
    score -= shock * 0.05
    score -= vol_enc * 0.10
    score += (stable_health - 0.5) * 0.10
    score += (predictor_conf - 0.5) * 0.15
    score += (exec_quality - 0.5) * 0.05

    prob = max(0.05, min(0.95, score))
    confidence = 0.3 + predictor_conf * 0.3 + stable_health * 0.2

    return {
        "probability": round(prob, 4),
        "prediction": 1 if prob > 0.5 else 0,
        "confidence": round(min(confidence, 0.75), 3),
        "model_type": "heuristic_fallback",
    }


def predict(features: dict[str, float]) -> dict[str, Any]:
    global _CACHED_PREDICTION

    model_data = get_trained_model()

    if model_data is None:
        pred = _heuristic_predict(features)
    else:
        try:
            model = model_data["model"]
            scaler = model_data.get("scaler")
            vec = [features_to_vector(features)]

            if scaler is not None:
                vec = scaler.transform(vec)

            prob = float(model.predict_proba(vec)[0][1])
            pred_class = int(model.predict(vec)[0])

            pred = {
                "probability": round(prob, 4),
                "prediction": pred_class,
                "confidence": round(min(0.85, model_data.get("train_accuracy", 0.5)), 3),
                "model_type": model_data.get("type", "unknown"),
            }
        except Exception as exc:
            logger.warning("ML inference failed, using heuristic: %s", exc)
            pred = _heuristic_predict(features)

    pred["ts"] = datetime.now(timezone.utc).isoformat()
    _CACHED_PREDICTION = pred
    return pred


def get_cached_prediction() -> dict[str, Any] | None:
    return _CACHED_PREDICTION
