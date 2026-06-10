import pytest
def test_yfinance_provider_fallback(monkeypatch):
    import backend.ingest.yfinance_ingest as yf_ingest

    class BadTicker:
        def history(self, *args, **kwargs):
            raise RuntimeError("provider down")

    class BadYF:
        @staticmethod
        def Ticker(_ticker):
            return BadTicker()

    monkeypatch.setitem(__import__('sys').modules, 'yfinance', BadYF)
    result = yf_ingest.fetch_history("SPY")
    assert result["degraded"] is True
    assert result["provider_status"]["status"] == "degraded"
    assert len(result["history"]) > 0


def test_equity_analytics_calculations():
    from backend.compute.equity_analytics import analyze_history
    hist = [{"ts": f"2026-01-{i:02d}T00:00:00+00:00", "close": 100 + i, "volume": 1000 + i} for i in range(1, 31)]
    spy = [{"ts": f"2026-01-{i:02d}T00:00:00+00:00", "close": 200 + i, "volume": 1000 + i} for i in range(1, 31)]
    row = analyze_history("ABC", hist, spy, "Technology")
    assert row["daily_return"] > 0
    assert row["return_5d"] > 0
    assert row["realized_volatility"] >= 0
    assert 0 <= row["max_drawdown"] <= 1
    assert 0 <= row["rsi"] <= 100
    assert "relative_strength_vs_spy" in row


def test_tariff_exposure_with_and_without_wits_gdelt():
    from backend.compute.equity_tariff_exposure import score_equity_exposure
    analytics = {"ticker": "AAPL", "sector": "Technology", "return_5d": -0.03, "volume_vs_avg": 1.5, "realized_volatility": 0.4, "relative_strength_vs_spy": -0.02}
    degraded = score_equity_exposure(analytics)
    full = score_equity_exposure(analytics, {"tariff_pressure": 75}, {"shock_score": 1.5})
    assert degraded["degraded"] is True
    assert full["degraded"] is False
    assert full["score"] >= degraded["score"]
    assert full["reasoning"]


def test_equity_agent_signal_structure():
    from backend.agents.equity_risk_agent import EquityRiskAgent
    signals = EquityRiskAgent().evaluate([{"ticker": "AAPL", "volume_vs_avg": 2.0, "relative_strength_vs_spy": -0.05, "realized_volatility": 0.2, "data_ts": "2026-01-01T00:00:00+00:00"}])
    assert signals
    required = {"agent", "ticker", "signal", "confidence", "severity", "direction", "proposed_action", "reason", "ts", "data_ts_used"}
    assert required.issubset(signals[0])


def test_equity_endpoints_fail_open():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    for path in ["/api/equities/overview", "/api/equities/quote/SPY", "/api/equities/history/SPY", "/api/equities/watchlist", "/api/equities/risk", "/api/equities/tariff-exposure", "/api/equities/sector-rotation", "/api/equities/cross-asset"]:
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert isinstance(resp.json(), dict)


def test_missing_external_data_does_not_crash_data_quality():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    resp = client.get("/api/health/data-quality")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert any(s["name"] == "yfinance" for s in data["sources"])


def test_allocation_execution_preview_structure():
    from backend.compute.capital_allocator import execution_preview, allocate
    result = execution_preview({"venue": "hyperliquid", "market": "SOL-PERP", "size": 1000, "price": 100, "available_cash": 5000}, allocate({}))
    assert result["auto_trade"] is False
    assert "allowed_size" in result
    assert "suggested_size" in result
    assert "warnings" in result
