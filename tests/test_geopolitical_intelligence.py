from fastapi.testclient import TestClient

from main import app
from backend.compute.geopolitical_risk import compute_geopolitical_index, build_geopolitical_events
from backend.compute.sanctions_risk import score_sanctions, sanctions_impact, sanctions_entities
from backend.compute.conflict_escalation import score_conflicts, conflict_market_impact
from backend.compute.shipping_energy_risk import score_chokepoints, score_energy_shock, supply_chain_impact
from backend.compute.geopolitical_market_impact import estimate_market_impact
from backend.compute.portfolio_protection import protection_protocol
from backend.agents.geopolitical_agent import GeopoliticalAgent
from backend.agents.sanctions_agent import SanctionsAgent
from backend.agents.conflict_agent import ConflictAgent
from backend.agents.energy_shock_agent import EnergyShockAgent
from backend.agents.protection_agent import ProtectionAgent

client = TestClient(app)


def test_geopolitical_index_fail_open_shape():
    idx = compute_geopolitical_index({})
    assert 0 <= idx["overall_score"] <= 100
    assert idx["regime"] in {"calm", "watch", "elevated", "high_risk", "crisis"}
    assert idx["data_quality"] in {"degraded", "partial", "healthy"}
    assert isinstance(idx["provider_status"], dict)
    assert isinstance(idx["regional_breakdown"], dict)
    assert isinstance(build_geopolitical_events(idx)["events"], list)


def test_component_engines_fail_open_and_score():
    sanctions = score_sanctions(None, None, None)
    assert 0 <= sanctions["sanctions_score"] <= 100
    assert sanctions["data_quality"] == "degraded"
    assert sanctions_impact(sanctions)["impacts"]
    assert sanctions_entities(None)["data_quality"] == "degraded"

    conflicts = score_conflicts(None)
    assert 0 <= conflicts["conflict_score"] <= 100
    assert conflicts["hotspots"]
    assert conflict_market_impact(conflicts)["impacts"]

    shipping = score_chokepoints(None)
    assert 0 <= shipping["shipping_score"] <= 100
    assert shipping["chokepoints"]
    assert supply_chain_impact(shipping)["impacts"]

    energy = score_energy_shock(None, sanctions)
    assert 0 <= energy["energy_shock_score"] <= 100
    assert "XLE" in energy["affected_assets"]


def test_market_impact_and_protection_are_proposal_only():
    idx = compute_geopolitical_index({"stablecoin": {"stress_score": 20}})
    events = build_geopolitical_events(idx)["events"]
    impact = estimate_market_impact(idx, events)
    assert impact["impacts"]
    assert {"asset", "asset_class", "impact_score", "direction", "suggested_risk_action"} <= set(impact["impacts"][0])

    protection = protection_protocol({"geopolitical_index": {**idx, "overall_score": 80}, "data_quality": "degraded"})
    assert protection["proposal_only"] is True
    assert protection["auto_trade"] is False
    assert protection["protection_mode"] in {"NORMAL", "WATCH", "DEFENSIVE", "CRISIS"}
    assert protection["recommended_actions"]


def test_geopolitical_agent_signal_structure():
    idx = compute_geopolitical_index({})
    idx["overall_score"] = 80
    idx["regime"] = "high_risk"
    protection = protection_protocol({"geopolitical_index": idx})
    signals = (
        GeopoliticalAgent().evaluate(idx)
        + SanctionsAgent().evaluate(idx)
        + ConflictAgent().evaluate(idx)
        + EnergyShockAgent().evaluate(idx)
        + ProtectionAgent().evaluate({**idx, **protection})
    )
    assert signals
    required = {"agent", "signal", "confidence", "severity", "direction", "proposed_action", "reason", "ts", "data_ts_used", "affected_assets", "affected_regions", "data_quality"}
    assert required <= set(signals[0])
    assert all("trade" not in s["proposed_action"].lower() for s in signals)


def test_geopolitical_endpoint_shapes():
    get_paths = [
        "/api/geopolitical/index",
        "/api/geopolitical/events",
        "/api/geopolitical/sanctions",
        "/api/geopolitical/sanctions/impact",
        "/api/geopolitical/sanctions/entities",
        "/api/geopolitical/conflicts",
        "/api/geopolitical/conflict/hotspots",
        "/api/geopolitical/conflict/escalation",
        "/api/geopolitical/conflict/market-impact",
        "/api/geopolitical/chokepoints",
        "/api/geopolitical/shipping-risk",
        "/api/geopolitical/supply-chain-impact",
        "/api/geopolitical/energy-shock",
        "/api/geopolitical/commodity-impact",
        "/api/geopolitical/market-impact",
        "/api/geopolitical/scenario-templates",
        "/api/protection/status",
        "/api/geopolitical/agents/signals",
        "/api/geopolitical/reports/daily-brief",
        "/api/geopolitical/reports/protection-brief",
    ]
    for path in get_paths:
        res = client.get(path)
        assert res.status_code == 200, path
        assert isinstance(res.json(), dict), path

    scenario = client.post("/api/geopolitical/scenario-run", json={"scenario_name": "Taiwan semiconductor shock", "severity": 75})
    assert scenario.status_code == 200
    body = scenario.json()
    assert body["protection_mode"] in {"NORMAL", "WATCH", "DEFENSIVE", "CRISIS"}
    assert body["agent_signals"]
    assert "No orders submitted" in body["reasoning"]

    preview = client.post("/api/protection/preview", json={"portfolio_risk": 70})
    assert preview.status_code == 200
    assert preview.json()["proposal_only"] is True


def test_geopolitical_frontend_safe_payloads_allow_empty_inputs():
    idx = compute_geopolitical_index({"gdelt": {}, "wits": {}, "stablecoin": {}, "cross_asset": {}})
    payloads = [
        build_geopolitical_events(idx),
        estimate_market_impact(idx, []),
        protection_protocol({"geopolitical_index": idx}),
    ]
    for payload in payloads:
        assert isinstance(payload, dict)
        assert payload.get("data_quality") or payload.get("timestamp") or payload.get("proposal_only")
