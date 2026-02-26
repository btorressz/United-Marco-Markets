import pytest
from unittest.mock import MagicMock, patch
from backend.execution.paper_exec import PaperExecutor
from backend.core.event_bus import EventBus, EventType
from backend.compute.risk_engine import RiskEngine


class TestPaperBuy:

    @pytest.fixture
    def executor(self):
        bus = MagicMock(spec=EventBus)
        return PaperExecutor(event_bus=bus)

    def test_buy_creates_long_position(self, executor):
        result = executor.place_order(
            venue="paper", market="SOL-PERP", side="buy", size=1.0, price=150.0,
            data_context={"execution_mode": "paper", "integrity_status": "OK"},
        )
        assert result["status"] == "paper_filled"
        assert result["fill_price"] == 150.0
        assert result["side"] == "buy"

        positions = executor.get_positions()
        assert len(positions) == 1
        assert positions[0]["size"] == 1.0
        assert positions[0]["side"] == "long"
        assert positions[0]["entry_price"] == 150.0

    def test_buy_emits_events(self, executor):
        executor.place_order(
            venue="paper", market="SOL-PERP", side="buy", size=1.0, price=150.0,
        )
        calls = executor.event_bus.emit.call_args_list
        event_types = [c[0][0] for c in calls]
        assert EventType.ORDER_SENT in event_types
        assert EventType.ORDER_FILLED in event_types

    def test_buy_event_payload_has_message(self, executor):
        executor.place_order(
            venue="paper", market="SOL-PERP", side="buy", size=2.5, price=140.0,
        )
        filled_call = [c for c in executor.event_bus.emit.call_args_list if c[0][0] == EventType.ORDER_FILLED][0]
        payload = filled_call[1]["payload"]
        assert "BUY" in payload["message"]
        assert "SOL-PERP" in payload["message"]


class TestPaperSell:

    @pytest.fixture
    def executor(self):
        bus = MagicMock(spec=EventBus)
        return PaperExecutor(event_bus=bus)

    def test_sell_creates_short_position(self, executor):
        result = executor.place_order(
            venue="paper", market="SOL-PERP", side="sell", size=1.0, price=150.0,
            data_context={"execution_mode": "paper", "integrity_status": "OK"},
        )
        assert result["status"] == "paper_filled"
        assert result["fill_price"] == 150.0
        assert result["side"] == "sell"

        positions = executor.get_positions()
        assert len(positions) == 1
        assert positions[0]["size"] == -1.0
        assert positions[0]["side"] == "short"

    def test_sell_emits_events(self, executor):
        executor.place_order(
            venue="paper", market="SOL-PERP", side="sell", size=1.0, price=150.0,
        )
        calls = executor.event_bus.emit.call_args_list
        event_types = [c[0][0] for c in calls]
        assert EventType.ORDER_SENT in event_types
        assert EventType.ORDER_FILLED in event_types

    def test_sell_event_payload_has_message(self, executor):
        executor.place_order(
            venue="paper", market="SOL-PERP", side="sell", size=1.0, price=150.0,
        )
        filled_call = [c for c in executor.event_bus.emit.call_args_list if c[0][0] == EventType.ORDER_FILLED][0]
        payload = filled_call[1]["payload"]
        assert "SELL" in payload["message"]

    def test_sell_reduces_existing_long(self, executor):
        executor.place_order(venue="paper", market="SOL-PERP", side="buy", size=2.0, price=150.0)
        executor.place_order(venue="paper", market="SOL-PERP", side="sell", size=1.0, price=155.0)

        positions = executor.get_positions()
        assert len(positions) == 1
        assert positions[0]["size"] == 1.0
        assert positions[0]["side"] == "long"

    def test_sell_closes_existing_long(self, executor):
        executor.place_order(venue="paper", market="SOL-PERP", side="buy", size=1.0, price=150.0)
        executor.place_order(venue="paper", market="SOL-PERP", side="sell", size=1.0, price=155.0)

        positions = executor.get_positions()
        assert len(positions) == 0

    def test_sell_flips_long_to_short(self, executor):
        executor.place_order(venue="paper", market="SOL-PERP", side="buy", size=1.0, price=150.0)
        executor.place_order(venue="paper", market="SOL-PERP", side="sell", size=2.0, price=155.0)

        positions = executor.get_positions()
        assert len(positions) == 1
        assert positions[0]["size"] == -1.0
        assert positions[0]["side"] == "short"

    def test_buy_closes_existing_short(self, executor):
        executor.place_order(venue="paper", market="SOL-PERP", side="sell", size=1.0, price=150.0)
        executor.place_order(venue="paper", market="SOL-PERP", side="buy", size=1.0, price=145.0)

        positions = executor.get_positions()
        assert len(positions) == 0


class TestRiskEngineReducing:

    @pytest.fixture
    def engine(self):
        return RiskEngine(max_leverage=3.0, max_margin_pct=0.6, max_daily_loss=500.0, cooldown_seconds=0)

    def test_sell_allowed_when_reducing_long(self, engine):
        positions = [
            {"venue": "paper", "market": "SOL-PERP", "size": 2.0, "entry_price": 150.0, "margin": 100.0},
        ]
        proposed = {"venue": "paper", "market": "SOL-PERP", "side": "sell", "size": 1.0, "price": 150.0}

        allowed, reasons = engine.check_constraints(positions, proposed, execution_mode="paper")
        assert allowed is True

    def test_sell_allowed_despite_daily_loss(self, engine):
        engine.daily_pnl = -600.0
        engine.daily_pnl_reset_date = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d")

        positions = [
            {"venue": "paper", "market": "SOL-PERP", "size": 2.0, "entry_price": 150.0, "margin": 100.0},
        ]
        proposed = {"venue": "paper", "market": "SOL-PERP", "side": "sell", "size": 1.0, "price": 150.0}

        allowed, reasons = engine.check_constraints(positions, proposed, execution_mode="paper")
        assert allowed is True
        assert not any("Daily loss" in r for r in reasons)

    def test_sell_allowed_despite_throttle(self, engine):
        engine.activate_throttle("high risk")

        positions = [
            {"venue": "paper", "market": "SOL-PERP", "size": 2.0, "entry_price": 150.0, "margin": 100.0},
        ]
        proposed = {"venue": "paper", "market": "SOL-PERP", "side": "sell", "size": 1.0, "price": 150.0}

        allowed, reasons = engine.check_constraints(positions, proposed, execution_mode="paper")
        assert not any("Throttle" in r for r in reasons)

    def test_new_sell_not_reducing_small(self, engine):
        positions = []
        proposed = {"venue": "paper", "market": "SOL-PERP", "side": "sell", "size": 0.001, "price": 100.0, "margin": 0.0}

        allowed, reasons = engine.check_constraints(positions, proposed, execution_mode="paper")
        assert allowed is True

    def test_new_sell_blocked_by_leverage(self, engine):
        positions = []
        proposed = {"venue": "paper", "market": "SOL-PERP", "side": "sell", "size": 10.0, "price": 150.0}

        allowed, reasons = engine.check_constraints(positions, proposed, execution_mode="paper")
        assert allowed is False
        assert any("Leverage" in r for r in reasons)

    def test_buy_after_sell_no_cooldown_paper(self, engine):
        engine.cooldown_seconds = 300

        positions = []
        buy = {"venue": "paper", "market": "SOL-PERP", "side": "buy", "size": 0.01, "price": 100.0, "margin": 0.0}
        sell = {"venue": "paper", "market": "SOL-PERP", "side": "sell", "size": 0.01, "price": 100.0, "margin": 0.0}

        allowed1, _ = engine.check_constraints(positions, buy, execution_mode="paper")
        assert allowed1 is True

        allowed2, reasons2 = engine.check_constraints(positions, sell, execution_mode="paper")
        assert allowed2 is True
        assert not any("Cooldown" in r for r in reasons2)


class TestPositionSideField:

    @pytest.fixture
    def executor(self):
        bus = MagicMock(spec=EventBus)
        return PaperExecutor(event_bus=bus)

    def test_long_position_has_side_long(self, executor):
        executor.place_order(venue="paper", market="SOL-PERP", side="buy", size=1.0, price=150.0)
        positions = executor.get_positions()
        assert positions[0]["side"] == "long"

    def test_short_position_has_side_short(self, executor):
        executor.place_order(venue="paper", market="SOL-PERP", side="sell", size=1.0, price=150.0)
        positions = executor.get_positions()
        assert positions[0]["side"] == "short"

    def test_position_returns_all_fields(self, executor):
        executor.place_order(venue="paper", market="SOL-PERP", side="buy", size=1.0, price=150.0)
        pos = executor.get_positions()[0]
        assert "venue" in pos
        assert "market" in pos
        assert "size" in pos
        assert "entry_price" in pos
        assert "side" in pos
        assert "pnl" in pos
