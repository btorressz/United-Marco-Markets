import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class MicrostructureAnalyzer:

    def compute_orderbook_imbalance(self, bids: list[list[float]], asks: list[list[float]], levels: int = 10) -> dict:
        bid_vol = sum(qty for _, qty in bids[:levels]) if bids else 0.0
        ask_vol = sum(qty for _, qty in asks[:levels]) if asks else 0.0
        total = bid_vol + ask_vol

        if total == 0:
            imbalance = 0.0
        else:
            imbalance = (bid_vol - ask_vol) / total

        bias = "neutral"
        if imbalance > 0.2:
            bias = "bullish"
        elif imbalance < -0.2:
            bias = "bearish"

        liquidity_thin = total < 100.0

        return {
            "bid_volume": round(bid_vol, 2),
            "ask_volume": round(ask_vol, 2),
            "imbalance": round(imbalance, 4),
            "bias": bias,
            "liquidity_thin": liquidity_thin,
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    def detect_dislocation(
        self,
        prices: dict[str, float],
        threshold_bps: float = 30.0,
        min_venues: int = 2,
    ) -> list[dict]:
        alerts = []
        venues = list(prices.keys())
        if len(venues) < min_venues:
            return alerts

        venue_prices = [(v, p) for v, p in prices.items() if p and p > 0]
        if len(venue_prices) < 2:
            return alerts

        for i in range(len(venue_prices)):
            for j in range(i + 1, len(venue_prices)):
                v_a, p_a = venue_prices[i]
                v_b, p_b = venue_prices[j]
                mid = (p_a + p_b) / 2.0
                if mid == 0:
                    continue
                spread_bps = abs(p_a - p_b) / mid * 10000.0
                if spread_bps > threshold_bps:
                    alerts.append({
                        "type": "DISLOCATION_ALERT",
                        "venue_a": v_a,
                        "venue_b": v_b,
                        "price_a": round(p_a, 4),
                        "price_b": round(p_b, 4),
                        "spread_bps": round(spread_bps, 2),
                        "ts": datetime.now(timezone.utc).isoformat(),
                    })

        return alerts

    def detect_basis_opportunity(
        self,
        perp_price: float,
        spot_price: float,
        venue_perp: str = "hyperliquid",
        venue_spot: str = "kraken",
        threshold_bps: float = 20.0,
    ) -> dict | None:
        if spot_price == 0 or perp_price == 0:
            return None

        basis_bps = (perp_price - spot_price) / spot_price * 10000.0

        if abs(basis_bps) > threshold_bps:
            direction = "short_perp_long_spot" if basis_bps > 0 else "long_perp_short_spot"
            return {
                "type": "BASIS_OPPORTUNITY",
                "perp_venue": venue_perp,
                "spot_venue": venue_spot,
                "perp_price": round(perp_price, 4),
                "spot_price": round(spot_price, 4),
                "basis_bps": round(basis_bps, 2),
                "direction": direction,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        return None

    def compute_convergence_speed(self, spread_series: list[float], timestamps: list[float] | None = None) -> dict:
        if len(spread_series) < 3:
            return {"half_life": None, "mean_reversion_speed": 0.0}

        changes = [spread_series[i + 1] - spread_series[i] for i in range(len(spread_series) - 1)]
        levels = spread_series[:-1]

        if not levels or all(l == 0 for l in levels):
            return {"half_life": None, "mean_reversion_speed": 0.0}

        n = len(changes)
        sum_xy = sum(l * c for l, c in zip(levels, changes))
        sum_xx = sum(l * l for l in levels)

        if sum_xx == 0:
            return {"half_life": None, "mean_reversion_speed": 0.0}

        beta = sum_xy / sum_xx
        import math
        half_life = -math.log(2) / beta if beta < 0 else None

        return {
            "half_life": round(half_life, 2) if half_life is not None else None,
            "mean_reversion_speed": round(abs(beta), 6),
        }
