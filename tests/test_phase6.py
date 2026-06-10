import pytest
import math


class TestCapitalAllocator:
    def setup_method(self):
        from backend.compute.capital_allocator import allocate, VENUES
        self.allocate = allocate
        self.VENUES = VENUES

    def test_weights_sum_to_one(self):
        result = self.allocate()
        weights = result["weights"]
        total = sum(weights[v] for v in self.VENUES)
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"

    def test_all_venues_present(self):
        result = self.allocate()
        for venue in self.VENUES:
            assert venue in result["weights"]

    def test_weights_non_negative(self):
        result = self.allocate()
        for venue, w in result["weights"].items():
            assert w >= 0.0, f"{venue} weight is negative: {w}"

    def test_caps_respected(self):
        from backend.compute.capital_allocator import CAPS
        result = self.allocate()
        for venue, w in result["weights"].items():
            assert w <= CAPS[venue] + 1e-9, f"{venue} exceeds cap: {w} > {CAPS[venue]}"

    def test_floors_respected(self):
        from backend.compute.capital_allocator import FLOORS
        result = self.allocate()
        for venue, w in result["weights"].items():
            assert w >= FLOORS[venue] - 1e-9, f"{venue} below floor: {w} < {FLOORS[venue]}"

    def test_shock_shifts_to_defensive(self):
        normal = self.allocate({"tariff_shock": 0.1})
        shocked = self.allocate({"tariff_shock": 0.9})
        assert shocked["weights"]["stablecoins"] >= normal["weights"]["stablecoins"]
        assert shocked["weights"]["hyperliquid"] <= normal["weights"]["hyperliquid"]

    def test_high_vol_reduces_perps(self):
        low_vol = self.allocate({"vol_regime": "low"})
        high_vol = self.allocate({"vol_regime": "extreme"})
        assert high_vol["weights"]["hyperliquid"] <= low_vol["weights"]["hyperliquid"]
        assert high_vol["weights"]["cash"] >= low_vol["weights"]["cash"]

    def test_confidence_in_range(self):
        result = self.allocate()
        assert 0.0 <= result["confidence"] <= 1.0

    def test_has_reasoning(self):
        result = self.allocate()
        assert len(result["reasoning"]) > 0
        assert any("proposal" in r.lower() for r in result["reasoning"])

    def test_result_structure(self):
        result = self.allocate()
        assert "weights" in result
        assert "max_capital_per_venue" in result
        assert "max_capital_per_strategy" in result
        assert "risk_adjusted_expected_returns" in result
        assert "confidence" in result
        assert "reasoning" in result
        assert "ts" in result


class TestVolRegimeEngine:
    def setup_method(self):
        from backend.compute.vol_regime_engine import classify_regime, get_recommendations, REGIMES
        self.classify = classify_regime
        self.get_recs = get_recommendations
        self.REGIMES = REGIMES

    def test_valid_regime_returned(self):
        result = self.classify()
        assert result["regime"] in self.REGIMES

    def test_empty_state_defaults(self):
        result = self.classify({})
        assert result["regime"] in self.REGIMES
        assert 0.0 <= result["confidence"] <= 1.0

    def test_high_vol_detected(self):
        result = self.classify({"annualized_vol": 1.5, "shock_score": 2.0})
        assert result["regime"] in ("shock_regime", "high_volatility")

    def test_low_vol_detected(self):
        result = self.classify({"annualized_vol": 0.10, "shock_score": 0.1, "stable_health": 1.0})
        assert result["regime"] in ("low_volatility", "normal_volatility")

    def test_liquidity_crunch_detected(self):
        result = self.classify({"stable_health": 0.2, "orderbook_depth_score": 0.1, "exec_quality": 0.2})
        assert result["regime"] in ("liquidity_crunch", "shock_regime")

    def test_scores_all_present(self):
        result = self.classify()
        assert "scores" in result
        for regime in self.REGIMES:
            assert regime in result["scores"]

    def test_recommendations_for_all_regimes(self):
        for regime in self.REGIMES:
            recs = self.get_recs(regime, 0.7)
            assert "summary" in recs
            assert "leverage_adjustment" in recs
            assert "slippage_tolerance" in recs
            assert "hedge_aggressiveness" in recs
            assert recs["regime"] == regime

    def test_shock_regime_most_defensive(self):
        shock_recs = self.get_recs("shock_regime", 0.8)
        normal_recs = self.get_recs("normal_volatility", 0.8)
        shock_w = shock_recs["strategy_weight_changes"]
        normal_w = normal_recs["strategy_weight_changes"]
        assert shock_w.get("defensive", 0) >= normal_w.get("defensive", 0)


class TestBacktester:
    def setup_method(self):
        from backend.compute.backtester import run_backtest
        self.run = run_backtest

    def test_basic_run_returns_structure(self):
        result = self.run({"window_days": 10, "initial_capital": 1000})
        assert "total_return" in result
        assert "sharpe_ratio" in result
        assert "max_drawdown" in result
        assert "win_rate" in result
        assert "trade_count" in result
        assert "equity_curve" in result
        assert "ts" in result

    def test_equity_curve_non_empty(self):
        result = self.run({"window_days": 10})
        assert len(result["equity_curve"]) > 0

    def test_win_rate_in_range(self):
        result = self.run({"window_days": 20, "strategy": "momentum"})
        assert 0.0 <= result["win_rate"] <= 1.0

    def test_max_drawdown_non_negative(self):
        result = self.run({"window_days": 10})
        assert result["max_drawdown"] >= 0.0

    def test_var_cvar_non_negative(self):
        result = self.run({"window_days": 20})
        assert result["var_95"] >= 0.0
        assert result["cvar_95"] >= 0.0

    def test_per_strategy_pnl_present(self):
        result = self.run({"window_days": 10})
        assert "per_strategy_pnl" in result
        assert isinstance(result["per_strategy_pnl"], dict)

    def test_config_echoed(self):
        config = {"window_days": 15, "initial_capital": 5000, "strategy": "carry_arb"}
        result = self.run(config)
        cfg = result["config"]
        assert cfg["window_days"] == 15
        assert cfg["initial_capital"] == 5000
        assert cfg["strategy"] == "carry_arb"

    def test_deterministic(self):
        r1 = self.run({"window_days": 10, "initial_capital": 1000})
        r2 = self.run({"window_days": 10, "initial_capital": 1000})
        assert r1["total_return"] == r2["total_return"]


class TestMLFeatureStore:
    def setup_method(self):
        from backend.ml.feature_store import build_features, FEATURE_NAMES, features_to_vector
        self.build = build_features
        self.FEATURE_NAMES = FEATURE_NAMES
        self.to_vector = features_to_vector

    def test_all_features_present(self):
        result = self.build()
        features = result["features"]
        for name in self.FEATURE_NAMES:
            assert name in features, f"Missing feature: {name}"

    def test_correct_feature_count(self):
        result = self.build()
        assert len(result["features"]) == len(self.FEATURE_NAMES)

    def test_features_are_finite(self):
        result = self.build()
        for name, val in result["features"].items():
            assert math.isfinite(val), f"Feature {name} is not finite: {val}"

    def test_missing_data_handled(self):
        result = self.build(None)
        assert "features" in result
        assert len(result["features"]) > 0

    def test_quality_field_present(self):
        result = self.build()
        assert "quality" in result
        assert result["quality"]["all_present"] is True

    def test_feature_vector_correct_length(self):
        result = self.build()
        vec = self.to_vector(result["features"])
        assert len(vec) == len(self.FEATURE_NAMES)

    def test_vol_regime_encoding(self):
        low_result = self.build({"vol_regime": "low"})
        high_result = self.build({"vol_regime": "extreme"})
        assert low_result["features"]["vol_regime_encoded"] < high_result["features"]["vol_regime_encoded"]


class TestMLInference:
    def setup_method(self):
        from backend.ml.inference import predict, _heuristic_predict
        self.predict = predict
        self.heuristic = _heuristic_predict

    def test_heuristic_in_range(self):
        features = {"tariff_index": 50.0, "shock_score": 0.5, "stable_health": 0.9, "predictor_conf": 0.6}
        result = self.heuristic(features)
        assert 0.0 <= result["probability"] <= 1.0
        assert result["prediction"] in (0, 1)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_predict_without_model(self):
        from backend.ml import training
        original = training._TRAINED_MODEL
        training._TRAINED_MODEL = None
        try:
            features = {"tariff_index": 30.0, "shock_score": 0.0}
            result = self.predict(features)
            assert "probability" in result
            assert "model_type" in result
            assert result["model_type"] == "heuristic_fallback"
        finally:
            training._TRAINED_MODEL = original

    def test_predict_returns_ts(self):
        features = {}
        result = self.predict(features)
        assert "ts" in result


class TestMLTraining:
    def setup_method(self):
        from backend.ml.training import train_offline, MIN_SAMPLES
        self.train = train_offline
        self.MIN_SAMPLES = MIN_SAMPLES

    def test_insufficient_data_returns_clean_error(self):
        result = self.train(samples=[{"tariff_index": 30.0}], labels=[1], method="logistic")
        assert result["success"] is False
        assert "reason" in result
        assert "Insufficient" in result["reason"]

    def test_empty_data_handled(self):
        result = self.train(samples=[], labels=[], method="logistic")
        assert result["success"] is False

    def test_mismatched_lengths(self):
        samples = [{"tariff_index": i} for i in range(25)]
        labels = [1] * 10
        result = self.train(samples=samples, labels=labels)
        assert result["success"] is False

    def test_training_result_has_ts(self):
        result = self.train(samples=[], labels=[], method="logistic")
        assert "ts" in result


class TestRedisHealthFallback:
    def test_state_store_handles_no_redis(self):
        from backend.core.state_store import StateStore
        store = StateStore(redis_url="redis://localhost:19999")
        assert store.get_snapshot("nonexistent") is None

    def test_set_snapshot_returns_false_without_redis(self):
        from backend.core.state_store import StateStore
        store = StateStore(redis_url="redis://localhost:19999")
        result = store.set_snapshot("test_key", {"value": 1})
        assert result is False

    def test_get_risk_throttle_fallback(self):
        from backend.core.state_store import StateStore
        store = StateStore(redis_url="redis://localhost:19999")
        result = store.get_risk_throttle()
        assert result["active"] is False

    def test_cached_computation_does_not_crash(self):
        from backend.core.state_store import StateStore
        store = StateStore(redis_url="redis://localhost:19999")
        result = store.get_snapshot("desk:backtest:latest")
        assert result is None


class TestPortfolioRiskCalculations:
    def test_var_calculation(self):
        from backend.compute.backtester import _compute_var_cvar
        returns = [-0.05, -0.03, -0.02, 0.01, 0.02, 0.03, -0.08, -0.01, 0.04, 0.02,
                   -0.06, 0.01, 0.02, -0.04, 0.03, 0.01, -0.02, 0.05, -0.01, 0.02]
        var, cvar = _compute_var_cvar(returns, 0.95)
        assert var >= 0.0
        assert cvar >= var

    def test_max_drawdown(self):
        from backend.compute.backtester import _compute_max_drawdown
        curve = [1000, 1100, 900, 950, 800, 1000]
        dd = _compute_max_drawdown(curve)
        assert dd > 0.0
        assert dd < 1.0
        expected_dd = (1100 - 800) / 1100
        assert abs(dd - expected_dd) < 0.001

    def test_sharpe_ratio(self):
        from backend.compute.backtester import _compute_sharpe
        positive_returns = [0.01] * 252
        sharpe = _compute_sharpe(positive_returns)
        assert sharpe > 0

        mixed_returns = [0.01, -0.01] * 126
        sharpe_mixed = _compute_sharpe(mixed_returns)
        assert sharpe_mixed < sharpe
