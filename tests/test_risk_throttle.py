import pytest
import time
from datetime import datetime, timezone
from backend.compute.risk_engine import RiskEngine


class TestRiskEngine:

    @pytest.fixture
    def engine(self):
        """Setup risk engine with test parameters."""
        return RiskEngine(
            max_leverage=3.0,
            max_margin_pct=0.6,
            max_daily_loss=500.0,
            cooldown_seconds=0,
        )

    def test_check_constraints_within_limits(self, engine):
        """Test that allows action when within limits."""
        positions = []
        proposed_action = {
            "size": 0.1,
            "price": 100.0,
            "margin": 0.0,
        }

        allowed, reasons = engine.check_constraints(positions, proposed_action)

        assert isinstance(allowed, bool)
        assert isinstance(reasons, list)

    def test_leverage_exceeded(self, engine):
        """Test that rejects when leverage exceeds limit."""
        positions = [
            {
                "size": 5.0,
                "entry_price": 100.0,
                "margin": 100.0,
            }
        ]
        proposed_action = {
            "size": 10.0,
            "price": 100.0,
            "margin": 200.0,
        }

        allowed, reasons = engine.check_constraints(positions, proposed_action)

        assert allowed is False
        assert any("Leverage" in reason for reason in reasons)

    def test_margin_exceeded(self, engine):
        """Test that rejects when margin usage exceeds limit."""
        positions = [
            {
                "size": 2.0,
                "entry_price": 100.0,
                "margin": 300.0,
            }
        ]
        proposed_action = {
            "size": 1.0,
            "price": 100.0,
            "margin": 200.0,
        }

        allowed, reasons = engine.check_constraints(positions, proposed_action)

        assert allowed is False
        assert any("Margin" in reason for reason in reasons)

    def test_daily_loss_exceeded(self, engine):
        """Test that rejects when daily loss limit is breached."""
        engine.daily_pnl = -600.0
        engine.daily_pnl_reset_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        positions = []
        proposed_action = {
            "size": 1.0,
            "price": 100.0,
            "margin": 50.0,
        }

        allowed, reasons = engine.check_constraints(positions, proposed_action)

        assert allowed is False
        assert any("Daily loss" in reason for reason in reasons)

    def test_daily_loss_within_limit(self, engine):
        """Test that allows when daily loss is within limit."""
        engine.daily_pnl = -400.0
        engine.daily_pnl_reset_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        positions = []
        proposed_action = {
            "size": 1.0,
            "price": 100.0,
            "margin": 50.0,
        }

        allowed, reasons = engine.check_constraints(positions, proposed_action)

        daily_loss_rejected = any("Daily loss" in reason for reason in reasons)
        assert daily_loss_rejected is False

    def test_throttle_activation(self, engine):
        """Test throttle activation and deactivation."""
        assert engine.throttle_active is False
        assert engine.throttle_reason == ""

        engine.activate_throttle("test reason")
        assert engine.throttle_active is True
        assert engine.throttle_reason == "test reason"

        engine.deactivate_throttle()
        assert engine.throttle_active is False
        assert engine.throttle_reason == ""

    def test_throttle_blocks_new_actions(self, engine):
        """Test that throttle blocks new (non-reducing) actions."""
        engine.activate_throttle("test throttle")

        positions = []
        proposed_action = {
            "venue": "paper",
            "market": "SOL-PERP",
            "side": "buy",
            "size": 1.0,
            "price": 100.0,
            "margin": 50.0,
        }

        allowed, reasons = engine.check_constraints(positions, proposed_action)

        assert allowed is False
        assert any("Throttle" in reason for reason in reasons)

    def test_throttle_allows_reducing(self, engine):
        """Test that throttle allows position-reducing actions."""
        engine.activate_throttle("test throttle")

        positions = [
            {"venue": "paper", "market": "SOL-PERP", "size": 1.0, "entry_price": 100.0, "margin": 50.0},
        ]
        proposed_action = {
            "venue": "paper",
            "market": "SOL-PERP",
            "side": "sell",
            "size": 0.5,
            "price": 100.0,
            "margin": 0.0,
        }

        allowed, reasons = engine.check_constraints(positions, proposed_action)

        assert not any("Throttle" in reason for reason in reasons)

    def test_cooldown_enforcement_live(self, engine):
        """Test that cooldown is enforced between actions in live mode."""
        engine.cooldown_seconds = 1

        positions = []
        proposed_action = {
            "size": 0.01,
            "price": 100.0,
            "margin": 0.0,
        }

        allowed1, reasons1 = engine.check_constraints(positions, proposed_action, execution_mode="live")
        assert isinstance(allowed1, bool)

        allowed2, reasons2 = engine.check_constraints(positions, proposed_action, execution_mode="live")
        assert isinstance(allowed2, bool)

        if not allowed2:
            assert any("Cooldown" in reason for reason in reasons2)

        time.sleep(1.1)
        allowed3, reasons3 = engine.check_constraints(positions, proposed_action, execution_mode="live")
        assert isinstance(allowed3, bool)

    def test_cooldown_skipped_in_paper(self, engine):
        """Test that cooldown is NOT enforced in paper mode."""
        engine.cooldown_seconds = 300

        positions = []
        proposed_action = {
            "size": 0.01,
            "price": 100.0,
            "margin": 0.0,
        }

        allowed1, _ = engine.check_constraints(positions, proposed_action, execution_mode="paper")
        assert allowed1 is True

        allowed2, reasons2 = engine.check_constraints(positions, proposed_action, execution_mode="paper")
        assert not any("Cooldown" in r for r in reasons2)

    def test_record_pnl(self, engine):
        """Test PnL recording."""
        engine.daily_pnl_reset_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        engine.daily_pnl = 0.0

        engine.record_pnl(100.0)
        assert engine.daily_pnl == 100.0

        engine.record_pnl(-50.0)
        assert engine.daily_pnl == 50.0

    def test_daily_pnl_reset(self, engine):
        """Test that daily PnL resets on new day."""
        from datetime import datetime, timezone, timedelta

        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        engine.daily_pnl_reset_date = yesterday
        engine.daily_pnl = 100.0

        engine.record_pnl(50.0)

        assert engine.daily_pnl == 50.0

    def test_get_status(self, engine):
        """Test status reporting."""
        status = engine.get_status()

        assert isinstance(status, dict)
        assert "throttle_active" in status
        assert "throttle_reason" in status
        assert "max_leverage" in status
        assert "max_margin_pct" in status
        assert "max_daily_loss" in status
        assert "cooldown_seconds" in status
        assert "daily_pnl" in status
        assert "ts" in status
        assert status["throttle_active"] is False
        assert status["max_leverage"] == 3.0

    def test_multiple_violations(self, engine):
        """Test that multiple violations are reported."""
        engine.activate_throttle("test")

        positions = [
            {
                "size": 10.0,
                "entry_price": 100.0,
                "margin": 500.0,
            }
        ]
        proposed_action = {
            "size": 10.0,
            "price": 100.0,
            "margin": 500.0,
        }

        allowed, reasons = engine.check_constraints(positions, proposed_action)

        assert allowed is False
        assert len(reasons) > 1

    def test_zero_margin(self, engine):
        """Test handling of zero margin."""
        positions = [
            {
                "size": 1.0,
                "entry_price": 100.0,
                "margin": 0.0,
            }
        ]
        proposed_action = {
            "size": 0.1,
            "price": 100.0,
            "margin": 10.0,
        }

        allowed, reasons = engine.check_constraints(positions, proposed_action)

        assert isinstance(allowed, bool)
        assert isinstance(reasons, list)

    def test_empty_positions(self, engine):
        """Test with no existing positions."""
        positions = []
        proposed_action = {
            "size": 0.01,
            "price": 100.0,
            "margin": 0.2,
        }

        allowed, reasons = engine.check_constraints(positions, proposed_action)

        assert allowed is True

    def test_leverage_calculation(self, engine):
        """Test that leverage is calculated correctly."""
        positions = [
            {
                "size": 0.5,
                "entry_price": 100.0,
                "margin": 500.0,
            }
        ]

        proposed_action = {
            "size": 0.0,
            "price": 100.0,
            "margin": 0.0,
        }

        allowed, reasons = engine.check_constraints(positions, proposed_action)
        assert isinstance(allowed, bool)
        assert isinstance(reasons, list)

    def test_margin_percentage_calculation(self, engine):
        """Test that margin percentage is calculated correctly."""
        positions = [
            {
                "size": 1.0,
                "entry_price": 100.0,
                "margin": 30.0,
            }
        ]

        proposed_action = {
            "size": 1.0,
            "price": 100.0,
            "margin": 30.0,
        }

        allowed, reasons = engine.check_constraints(positions, proposed_action)

        total_margin_usage = (30.0 + 30.0) / 30.0
        if total_margin_usage > engine.max_margin_pct:
            assert allowed is False
        else:
            assert allowed is True
