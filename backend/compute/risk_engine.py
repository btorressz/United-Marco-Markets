import time
from datetime import datetime, timezone


class RiskEngine:

    def __init__(
        self,
        max_leverage: float = 3.0,
        max_margin_pct: float = 0.6,
        max_daily_loss: float = 500.0,
        cooldown_seconds: int = 300,
    ):
        self.max_leverage = max_leverage
        self.max_margin_pct = max_margin_pct
        self.max_daily_loss = max_daily_loss
        self.cooldown_seconds = cooldown_seconds

        self.throttle_active = False
        self.throttle_reason = ""
        self.last_action_ts: float = 0.0
        self.daily_pnl: float = 0.0
        self.daily_pnl_reset_date: str = ""

    def _is_reducing(self, positions: list[dict], proposed_action: dict) -> bool:
        side = proposed_action.get("side", "").lower()
        market = proposed_action.get("market", "")
        venue = proposed_action.get("venue", "")
        key = f"{venue}:{market}"
        for p in positions:
            p_key = f"{p.get('venue', '')}:{p.get('market', '')}"
            if p_key == key:
                p_size = p.get("size", 0)
                if (p_size > 0 and side == "sell") or (p_size < 0 and side == "buy"):
                    return True
        return False

    def check_constraints(
        self,
        positions: list[dict],
        proposed_action: dict,
        execution_mode: str = "paper",
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []

        is_reducing = self._is_reducing(positions, proposed_action)

        if self.throttle_active and not is_reducing:
            reasons.append(f"Throttle active: {self.throttle_reason}")

        total_notional = sum(abs(p.get("size", 0) * p.get("entry_price", 0)) for p in positions)
        total_margin = sum(p.get("margin", 0) for p in positions)
        total_equity = total_margin if total_margin > 0 else 1.0

        action_notional = abs(proposed_action.get("size", 0) * proposed_action.get("price", 0))

        if is_reducing:
            projected_notional = max(0, total_notional - action_notional)
        else:
            projected_notional = total_notional + action_notional

        projected_leverage = projected_notional / total_equity if total_equity > 0 else 0.0

        if not is_reducing and projected_leverage > self.max_leverage:
            reasons.append(
                f"Leverage limit exceeded: projected {projected_leverage:.2f} > max {self.max_leverage:.2f}"
            )

        if not is_reducing:
            action_margin = proposed_action.get("margin", action_notional / self.max_leverage)
            projected_margin_usage = (total_margin + action_margin) / total_equity if total_equity > 0 else 0.0
            if projected_margin_usage > self.max_margin_pct:
                reasons.append(
                    f"Margin usage exceeded: projected {projected_margin_usage:.2%} > max {self.max_margin_pct:.2%}"
                )

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self.daily_pnl_reset_date != today:
            self.daily_pnl = 0.0
            self.daily_pnl_reset_date = today

        if self.daily_pnl < -self.max_daily_loss and not is_reducing:
            reasons.append(
                f"Daily loss limit breached: {self.daily_pnl:.2f} < -{self.max_daily_loss:.2f}"
            )

        if execution_mode == "live" and not is_reducing:
            elapsed = time.time() - self.last_action_ts
            if self.last_action_ts > 0 and elapsed < self.cooldown_seconds:
                remaining = self.cooldown_seconds - elapsed
                reasons.append(f"Cooldown active: {remaining:.0f}s remaining")

        allowed = len(reasons) == 0
        if allowed:
            self.last_action_ts = time.time()

        return allowed, reasons

    def activate_throttle(self, reason: str) -> None:
        self.throttle_active = True
        self.throttle_reason = reason

    def deactivate_throttle(self) -> None:
        self.throttle_active = False
        self.throttle_reason = ""

    def record_pnl(self, pnl: float) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self.daily_pnl_reset_date != today:
            self.daily_pnl = 0.0
            self.daily_pnl_reset_date = today
        self.daily_pnl += pnl

    def get_status(self) -> dict:
        return {
            "throttle_active": self.throttle_active,
            "throttle_reason": self.throttle_reason,
            "max_leverage": self.max_leverage,
            "max_margin_pct": self.max_margin_pct,
            "max_daily_loss": self.max_daily_loss,
            "cooldown_seconds": self.cooldown_seconds,
            "daily_pnl": self.daily_pnl,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
