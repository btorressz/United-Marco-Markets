import pytest


def test_macro_events_fail_open_and_reaction_shape():
    from backend.compute.macro_events import build_macro_events, compute_impact
    events = build_macro_events(None, None)
    assert events["degraded"] is True
    assert events["events"]
    impact = compute_impact(events["events"])
    assert "reactions" in impact
    assert "avg_spy_reaction" in impact["summary"]


def test_macro_sensitivity_reasoned_score():
    from backend.compute.macro_sensitivity import score_asset_sensitivity
    result = score_asset_sensitivity({"ticker": "AAPL", "sector": "Technology", "relative_strength_vs_spy": -0.04, "realized_volatility": 0.5, "max_drawdown": 0.12, "volume_vs_avg": 1.8}, 15, 1.2, True)
    assert result["ticker"] == "AAPL"
    assert result["tariff_beta"] > 0
    assert result["degraded"] is True
    assert result["reasoning"]


def test_cross_asset_correlation_and_contagion():
    from backend.compute.cross_asset_intelligence import compute_correlations, demo_series, detect_contagion
    corr = compute_correlations(demo_series())
    assert "matrix" in corr
    assert any(r["asset"] == "SPY" for r in corr["matrix"])
    contagion = detect_contagion({"tariff_shock": 0.8, "equity_return": -0.03, "crypto_return": -0.025, "stablecoin_depeg_bps": 20, "semiconductor_return": -0.04})
    assert contagion["contagion_score"] > 0
    assert len(contagion["paths"]) == 4


def test_scenario_engine_safe_outputs():
    from backend.compute.scenario_engine import scenario_templates, run_scenario
    assert scenario_templates()["templates"]
    result = run_scenario({"tariff_index_change": 20, "gdelt_shock_change": 1, "equity_drawdown": -0.04, "crypto_drawdown": -0.03, "stablecoin_depeg": 10, "funding_flip": True, "liquidity_depth_drop": 0.3, "volatility_spike": 0.4})
    assert "portfolio_pnl_impact" in result
    assert result["agent_signals"]
    assert result["allocation_changes"]["cash"] >= 0.1
    assert "execution_warnings" in result


def test_hedge_explain_consensus_attribution_reports_watchlists():
    from backend.compute.cross_asset_hedging import recommend_cross_asset_hedges
    from backend.compute.portfolio_explainability import explain_portfolio
    from backend.compute.agent_consensus import build_consensus
    from backend.compute.signal_attribution import attribution_summary
    from backend.compute.report_generator import build_report
    from backend.compute.watchlists import list_watchlists, create_watchlist, update_watchlist, delete_watchlist
    signals = [{"agent": "a", "direction": "bearish", "confidence": 0.8, "signal": "RISK"}, {"agent": "b", "direction": "bullish", "confidence": 0.4, "signal": "BUY"}]
    assert recommend_cross_asset_hedges({"tariff_beta": 0.8})["proposal_only"] is True
    assert explain_portfolio({"confidence": 0.6}, signals)["proposal_only"] is True
    assert build_consensus(signals)["confidence_weighted_consensus"] in ("bullish", "bearish", "neutral")
    assert attribution_summary(signals)["signal_count"] == 2
    assert build_report("daily_brief")["sections"]
    wl = create_watchlist({"name": "Test", "assets": ["SPY"]})
    assert update_watchlist(wl["id"], {"assets": ["QQQ"]})["assets"] == ["QQQ"]
    assert delete_watchlist(wl["id"])["deleted"] is True
    assert list_watchlists()["watchlists"]


def test_institutional_endpoint_shapes_fail_open():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    for path in [
        "/api/macro/events", "/api/macro/events/impact", "/api/macro-sensitivity/assets",
        "/api/macro-sensitivity/SPY", "/api/cross-asset/correlations", "/api/cross-asset/contagion",
        "/api/scenario/templates", "/api/hedge/cross-asset", "/api/explain/portfolio",
        "/api/agents/consensus", "/api/signals/outcomes", "/api/signals/attribution",
        "/api/watchlists", "/api/reports/daily-brief", "/api/reports/tariff-risk",
        "/api/reports/portfolio-risk", "/api/reports/agent-signals",
    ]:
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert isinstance(resp.json(), dict)
    resp = client.post("/api/scenario/run", json={"tariff_index_change": 10})
    assert resp.status_code == 200
    assert "portfolio_pnl_impact" in resp.json()
