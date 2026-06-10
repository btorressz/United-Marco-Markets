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


def test_new_routers_registered_once_and_existing_routes_present():
    from collections import Counter
    from main import app
    expected = {
        "/api/macro/events", "/api/macro/events/impact", "/api/macro/events/{event_id}/reaction",
        "/api/macro-sensitivity/assets", "/api/macro-sensitivity/{ticker}",
        "/api/cross-asset/correlations", "/api/cross-asset/contagion",
        "/api/scenario/templates", "/api/scenario/run", "/api/explain/portfolio",
        "/api/explain/recommendation/{rec_id}", "/api/signals/outcomes", "/api/signals/attribution",
        "/api/watchlists", "/api/reports/daily-brief", "/api/equities/overview", "/api/strategy/performance",
        "/api/index/latest", "/api/execution/order", "/api/risk/status",
    }
    routes = [(tuple(sorted(route.methods)), route.path) for route in app.routes if hasattr(route, "methods")]
    counts = Counter(routes)
    assert not [item for item, count in counts.items() if count > 1]
    paths = {path for _methods, path in routes}
    assert expected.issubset(paths)


def test_all_requested_institutional_endpoints_available_with_safe_json():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    events = client.get("/api/macro/events").json()["events"]
    event_id = events[0]["id"] if events else "fallback"
    checks = [
        ("GET", "/api/macro/events", None),
        ("GET", "/api/macro/events/impact", None),
        ("GET", f"/api/macro/events/{event_id}/reaction", None),
        ("GET", "/api/macro-sensitivity/assets", None),
        ("GET", "/api/cross-asset/correlations", None),
        ("GET", "/api/cross-asset/contagion", None),
        ("GET", "/api/scenario/templates", None),
        ("POST", "/api/scenario/run", {"tariff_index_change": 10}),
        ("GET", "/api/hedge/cross-asset", None),
        ("POST", "/api/hedge/preview", {"tariff_beta": 0.8}),
        ("GET", "/api/explain/portfolio", None),
        ("GET", "/api/agents/consensus", None),
        ("GET", "/api/signals/outcomes", None),
        ("GET", "/api/signals/attribution", None),
        ("GET", "/api/watchlists", None),
        ("GET", "/api/reports/daily-brief", None),
        ("GET", "/api/reports/tariff-risk", None),
        ("GET", "/api/reports/portfolio-risk", None),
        ("GET", "/api/reports/agent-signals", None),
    ]
    for method, path, body in checks:
        response = client.request(method, path, json=body)
        assert response.status_code == 200, path
        assert isinstance(response.json(), dict), path


def test_provider_storage_and_empty_dataset_fail_open(monkeypatch):
    from backend.compute.cross_asset_intelligence import compute_correlations
    from backend.compute.macro_sensitivity import score_assets
    from backend.compute.macro_events import build_macro_events
    from backend.core.state_store import StateStore
    from backend.ingest import stooq_ingest
    import backend.api.health_routes as health_routes

    def raise_urlopen(*_args, **_kwargs):
        raise RuntimeError("stooq unavailable")

    monkeypatch.setattr(stooq_ingest.urllib.request, "urlopen", raise_urlopen)
    stooq = stooq_ingest.fetch_history("SPY")
    assert stooq["degraded"] is True
    assert stooq["history"]

    assert build_macro_events(None, None)["degraded"] is True
    assert compute_correlations({})["degraded"] is True
    assert score_assets([], 0, 0, True)["assets"] == []
    assert StateStore(redis_url="redis://localhost:19999").get_snapshot("missing") is None

    monkeypatch.setattr(health_routes, "check_connection", lambda: False)
    health = health_routes.health_check().model_dump()
    assert health["database"] is False
    assert health["status"] == "degraded"
