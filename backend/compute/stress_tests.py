from datetime import datetime, timezone


class StressTestRunner:

    def __init__(self, maintenance_margin_pct: float = 0.05):
        self.maintenance_margin_pct = maintenance_margin_pct
        self.scenarios = {
            "tariff_shock": self._tariff_shock,
            "sol_crash": self._sol_crash,
            "vol_spike": self._vol_spike,
        }

    def run_scenario(
        self,
        scenario_name: str,
        positions: list[dict],
        params: dict | None = None,
    ) -> dict:
        params = params or {}
        handler = self.scenarios.get(scenario_name)
        if handler is None:
            return {
                "scenario": scenario_name,
                "error": f"Unknown scenario: {scenario_name}",
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        return handler(positions, params)

    def _tariff_shock(self, positions: list[dict], params: dict) -> dict:
        shock_pct = params.get("shock_pct", 10.0) / 100.0
        sensitivity = params.get("sensitivity", 0.3)

        total_notional = 0.0
        total_margin = 0.0
        pnl_impact = 0.0
        venue_details = {}

        for pos in positions:
            size = pos.get("size", 0.0)
            price = pos.get("entry_price", 0.0)
            margin = pos.get("margin", 0.0)
            venue = pos.get("venue", "unknown")
            notional = abs(size * price)
            total_notional += notional
            total_margin += margin

            pos_pnl = -notional * shock_pct * sensitivity * (1 if size > 0 else -1)
            pnl_impact += pos_pnl

            liq_price = pos.get("liq_price")
            stressed_price = price * (1 - shock_pct * sensitivity)
            liq_dist = ((stressed_price - liq_price) / stressed_price * 100.0) if liq_price and stressed_price else None

            venue_details[venue] = {
                "notional": notional,
                "pnl_impact": round(pos_pnl, 2),
                "stressed_price": round(stressed_price, 4),
                "liquidation_distance_pct": round(liq_dist, 2) if liq_dist is not None else None,
            }

        equity = total_margin + pnl_impact
        margin_usage = total_margin / equity if equity > 0 else 1.0
        drawdown = (pnl_impact / total_margin * 100.0) if total_margin > 0 else 0.0

        return {
            "scenario": "tariff_shock",
            "price_shock_pct": params.get("shock_pct", 10.0),
            "projected_pnl": round(pnl_impact, 2),
            "projected_margin": round(margin_usage, 4),
            "would_liquidate": margin_usage > (1.0 - self.maintenance_margin_pct),
            "details": {
                "margin_usage_projected": round(margin_usage, 4),
                "drawdown_projected": round(drawdown, 2),
                "liquidation_distances": venue_details,
            },
        }

    def _sol_crash(self, positions: list[dict], params: dict) -> dict:
        crash_pct = params.get("crash_pct", 8.0) / 100.0

        total_margin = 0.0
        pnl_impact = 0.0
        venue_details = {}

        for pos in positions:
            size = pos.get("size", 0.0)
            price = pos.get("entry_price", 0.0)
            margin = pos.get("margin", 0.0)
            venue = pos.get("venue", "unknown")
            notional = abs(size * price)
            total_margin += margin

            price_change = -crash_pct if size > 0 else crash_pct
            pos_pnl = size * price * price_change
            pnl_impact += pos_pnl

            liq_price = pos.get("liq_price")
            stressed_price = price * (1 - crash_pct)
            liq_dist = ((stressed_price - liq_price) / stressed_price * 100.0) if liq_price and stressed_price else None

            venue_details[venue] = {
                "notional": notional,
                "pnl_impact": round(pos_pnl, 2),
                "stressed_price": round(stressed_price, 4),
                "liquidation_distance_pct": round(liq_dist, 2) if liq_dist is not None else None,
            }

        equity = total_margin + pnl_impact
        margin_usage = total_margin / equity if equity > 0 else 1.0
        drawdown = (pnl_impact / total_margin * 100.0) if total_margin > 0 else 0.0

        return {
            "scenario": "sol_crash",
            "price_shock_pct": params.get("crash_pct", 8.0),
            "projected_pnl": round(pnl_impact, 2),
            "projected_margin": round(margin_usage, 4),
            "would_liquidate": margin_usage > (1.0 - self.maintenance_margin_pct),
            "details": {
                "margin_usage_projected": round(margin_usage, 4),
                "drawdown_projected": round(drawdown, 2),
                "liquidation_distances": venue_details,
            },
        }

    def _vol_spike(self, positions: list[dict], params: dict) -> dict:
        vol_multiplier = params.get("vol_multiplier", 2.0)
        base_margin_rate = params.get("base_margin_rate", 0.05)

        total_margin_current = 0.0
        total_notional = 0.0
        venue_details = {}

        for pos in positions:
            size = pos.get("size", 0.0)
            price = pos.get("entry_price", 0.0)
            margin = pos.get("margin", 0.0)
            venue = pos.get("venue", "unknown")
            notional = abs(size * price)
            total_notional += notional
            total_margin_current += margin

            new_margin_rate = base_margin_rate * vol_multiplier
            required_margin = notional * new_margin_rate
            margin_increase = required_margin - margin

            liq_price = pos.get("liq_price")
            liq_dist = ((price - liq_price) / price * 100.0) if liq_price and price else None

            venue_details[venue] = {
                "notional": notional,
                "current_margin": round(margin, 2),
                "required_margin": round(required_margin, 2),
                "margin_increase": round(margin_increase, 2),
                "liquidation_distance_pct": round(liq_dist, 2) if liq_dist is not None else None,
            }

        total_required = total_notional * base_margin_rate * vol_multiplier
        margin_usage = total_required / total_margin_current if total_margin_current > 0 else 1.0
        shortfall = max(total_required - total_margin_current, 0.0)

        return {
            "scenario": "vol_spike",
            "price_shock_pct": 0.0,
            "projected_pnl": 0.0,
            "projected_margin": round(margin_usage, 4),
            "would_liquidate": margin_usage > 1.0,
            "details": {
                "margin_usage_projected": round(margin_usage, 4),
                "drawdown_projected": 0.0,
                "vol_multiplier": vol_multiplier,
                "margin_shortfall": round(shortfall, 2),
                "liquidation_distances": venue_details,
            },
        }
