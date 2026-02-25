from datetime import datetime, timezone


class RulesEngine:

    def __init__(self):
        self.rules = [
            {
                "name": "tariff_vol_reduce",
                "condition": self._tariff_vol_condition,
                "action_type": "reduce_exposure",
                "explanation": "Tariff index rate_of_change > 5 and vol regime is high -> reduce exposure",
            },
            {
                "name": "shock_throttle",
                "condition": self._shock_condition,
                "action_type": "enable_risk_throttle",
                "explanation": "Shock score > 2.0 -> enable risk throttle",
            },
            {
                "name": "divergence_hedge",
                "condition": self._divergence_hedge_condition,
                "action_type": "hedge",
                "explanation": "Divergence alert active and funding regime flipped -> hedge",
            },
            {
                "name": "negative_carry_reduce",
                "condition": self._negative_carry_condition,
                "action_type": "reduce_long_perp",
                "explanation": "Carry score very negative -> reduce long perp",
            },
            {
                "name": "stable_rotation",
                "condition": self._stable_rotation_condition,
                "action_type": "rotate_to_stables",
                "explanation": "Tariff shock high -> rotate to 80% stables, reduce beta to 0.2",
            },
        ]

    def evaluate(self, context: dict) -> list[dict]:
        actions: list[dict] = []
        for rule in self.rules:
            if rule["condition"](context):
                actions.append({
                    "rule_name": rule["name"],
                    "action_type": rule["action_type"],
                    "venue": context.get("venue", ""),
                    "market": context.get("market", ""),
                    "side": self._infer_side(rule["action_type"]),
                    "size": context.get("suggested_size", 0.0),
                    "reason": rule["explanation"],
                    "ts": datetime.now(timezone.utc).isoformat(),
                })
        return actions

    def _tariff_vol_condition(self, ctx: dict) -> bool:
        roc = ctx.get("tariff_rate_of_change", 0.0)
        vol_regime = ctx.get("vol_regime", "normal")
        return roc > 5.0 and vol_regime in ("high", "extreme")

    def _shock_condition(self, ctx: dict) -> bool:
        return ctx.get("shock_score", 0.0) > 2.0

    def _divergence_hedge_condition(self, ctx: dict) -> bool:
        divergence_active = ctx.get("divergence_alert_active", False)
        regime_flipped = ctx.get("funding_regime_flipped", False)
        return divergence_active and regime_flipped

    def _negative_carry_condition(self, ctx: dict) -> bool:
        return ctx.get("carry_score", 0.0) < -0.10

    def _stable_rotation_condition(self, ctx: dict) -> bool:
        shock = ctx.get("shock_score", 0.0)
        tariff_roc = ctx.get("tariff_rate_of_change", 0.0)
        return shock > 1.5 or tariff_roc > 8.0

    def _infer_side(self, action_type: str) -> str:
        if action_type in ("reduce_exposure", "reduce_long_perp", "rotate_to_stables"):
            return "sell"
        if action_type == "hedge":
            return "sell"
        return "none"
