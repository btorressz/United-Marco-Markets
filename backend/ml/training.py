import logging
from datetime import datetime, timezone
from typing import Any

from backend.ml.feature_store import FEATURE_NAMES, features_to_vector

logger = logging.getLogger(__name__)

_TRAINED_MODEL: dict[str, Any] | None = None
_TRAINING_HISTORY: list[dict[str, Any]] = []

MIN_SAMPLES = 20


def _try_import_sklearn():
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import cross_val_score
        return LogisticRegression, StandardScaler, cross_val_score
    except ImportError:
        return None, None, None


def _try_import_lgbm():
    try:
        import lightgbm as lgb
        return lgb
    except ImportError:
        return None


def train_offline(
    samples: list[dict[str, Any]],
    labels: list[int],
    method: str = "logistic",
) -> dict[str, Any]:
    global _TRAINED_MODEL, _TRAINING_HISTORY

    if len(samples) < MIN_SAMPLES:
        return {
            "success": False,
            "reason": f"Insufficient training data: {len(samples)} samples, minimum {MIN_SAMPLES} required",
            "samples_provided": len(samples),
            "samples_needed": MIN_SAMPLES,
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    if len(samples) != len(labels):
        return {
            "success": False,
            "reason": "samples and labels length mismatch",
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    X = [features_to_vector(s.get("features", s)) for s in samples]
    y = [int(bool(lbl)) for lbl in labels]

    if method == "lgbm":
        lgb = _try_import_lgbm()
        if lgb is not None:
            return _train_lgbm(lgb, X, y)
        logger.warning("LightGBM not available, falling back to logistic regression")
        method = "logistic"

    LogisticRegression, StandardScaler, cross_val_score = _try_import_sklearn()
    if LogisticRegression is None:
        return {
            "success": False,
            "reason": "scikit-learn not installed",
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    return _train_sklearn(LogisticRegression, StandardScaler, cross_val_score, X, y)


def _train_sklearn(LR, Scaler, cv_score, X, y) -> dict[str, Any]:
    global _TRAINED_MODEL, _TRAINING_HISTORY
    try:
        scaler = Scaler()
        X_scaled = scaler.fit_transform(X)
        model = LR(max_iter=500, C=1.0, random_state=42)
        model.fit(X_scaled, y)

        cv_scores = []
        try:
            cv_scores = cv_score(model, X_scaled, y, cv=min(5, len(y) // 4 + 1), scoring="accuracy").tolist()
        except Exception:
            pass

        acc = model.score(X_scaled, y)

        _TRAINED_MODEL = {
            "type": "sklearn_logistic",
            "model": model,
            "scaler": scaler,
            "feature_names": FEATURE_NAMES,
            "n_samples": len(X),
            "train_accuracy": round(acc, 4),
        }

        result = {
            "success": True,
            "method": "logistic_regression",
            "n_samples": len(X),
            "train_accuracy": round(acc, 4),
            "cv_scores": [round(s, 4) for s in cv_scores],
            "cv_mean": round(sum(cv_scores) / len(cv_scores), 4) if cv_scores else None,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        _TRAINING_HISTORY.append(result)
        _TRAINING_HISTORY = _TRAINING_HISTORY[-10:]
        return result
    except Exception as exc:
        logger.warning("sklearn training failed: %s", exc, exc_info=True)
        return {
            "success": False,
            "reason": str(exc),
            "ts": datetime.now(timezone.utc).isoformat(),
        }


def _train_lgbm(lgb, X, y) -> dict[str, Any]:
    global _TRAINED_MODEL, _TRAINING_HISTORY
    try:
        params = {
            "objective": "binary",
            "num_leaves": 16,
            "learning_rate": 0.05,
            "n_estimators": 50,
            "random_state": 42,
            "verbosity": -1,
        }
        model = lgb.LGBMClassifier(**params)
        model.fit(X, y)
        acc = model.score(X, y)

        _TRAINED_MODEL = {
            "type": "lgbm",
            "model": model,
            "scaler": None,
            "feature_names": FEATURE_NAMES,
            "n_samples": len(X),
            "train_accuracy": round(acc, 4),
        }

        result = {
            "success": True,
            "method": "lightgbm",
            "n_samples": len(X),
            "train_accuracy": round(acc, 4),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        _TRAINING_HISTORY.append(result)
        _TRAINING_HISTORY = _TRAINING_HISTORY[-10:]
        return result
    except Exception as exc:
        logger.warning("LightGBM training failed: %s", exc, exc_info=True)
        return {
            "success": False,
            "reason": str(exc),
            "ts": datetime.now(timezone.utc).isoformat(),
        }


def get_trained_model() -> dict[str, Any] | None:
    return _TRAINED_MODEL


def get_training_history() -> list[dict[str, Any]]:
    return list(_TRAINING_HISTORY)
