import logging
import math
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class StablecoinHealthMonitor:

    STABLES = ["USDC", "USDT", "DAI"]
    DEPEG_WARN_BPS = 20
    DEPEG_ALERT_BPS = 50
    VOLUME_SPIKE_Z = 2.0
    FUNDING_SPIKE_Z = 2.0

    def compute_depeg_bps(self, price: float, peg: float = 1.0) -> float:
        if peg == 0:
            return 0.0
        return abs(price - peg) / peg * 10000.0

    def compute_health(self, prices: dict[str, float], peg: float = 1.0) -> dict:
        results = {}
        for symbol, price in prices.items():
            depeg = self.compute_depeg_bps(price, peg)
            status = "ok"
            if depeg > self.DEPEG_ALERT_BPS:
                status = "alert"
            elif depeg > self.DEPEG_WARN_BPS:
                status = "warning"
            results[symbol] = {
                "price": price,
                "peg": peg,
                "depeg_bps": round(depeg, 2),
                "status": status,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        return results

    def compute_liquidity_depth(self, bids: list[list[float]], asks: list[list[float]], depth_bps: float = 50.0) -> dict:
        bid_depth = sum(qty for price, qty in bids[:10]) if bids else 0.0
        ask_depth = sum(qty for price, qty in asks[:10]) if asks else 0.0
        mid = 0.0
        spread_bps = 0.0
        if bids and asks:
            best_bid = bids[0][0]
            best_ask = asks[0][0]
            mid = (best_bid + best_ask) / 2.0
            spread_bps = ((best_ask - best_bid) / mid * 10000.0) if mid > 0 else 0.0

        return {
            "bid_depth": round(bid_depth, 2),
            "ask_depth": round(ask_depth, 2),
            "mid_price": round(mid, 6),
            "spread_bps": round(spread_bps, 2),
            "total_depth": round(bid_depth + ask_depth, 2),
        }

    def detect_stress(self, depeg_bps: float, volume_z: float, spread_bps: float) -> dict:
        stress_score = 0.0
        factors = []

        if depeg_bps > self.DEPEG_ALERT_BPS:
            stress_score += 0.4
            factors.append(f"depeg {depeg_bps:.0f}bps")
        elif depeg_bps > self.DEPEG_WARN_BPS:
            stress_score += 0.2
            factors.append(f"depeg {depeg_bps:.0f}bps")

        if volume_z > self.VOLUME_SPIKE_Z:
            stress_score += 0.3
            factors.append(f"volume z={volume_z:.1f}")

        if spread_bps > 30:
            stress_score += 0.3
            factors.append(f"spread {spread_bps:.0f}bps")

        return {
            "stress_score": round(min(stress_score, 1.0), 3),
            "is_stressed": stress_score > 0.5,
            "factors": factors,
        }

    def compute_peg_break_probability(self, depeg_bps: float, depeg_history: list[float] | None = None) -> float:
        if not depeg_history or len(depeg_history) < 5:
            if depeg_bps > self.DEPEG_ALERT_BPS:
                return min(depeg_bps / 200.0, 0.95)
            return min(depeg_bps / 500.0, 0.3)

        mean_d = sum(depeg_history) / len(depeg_history)
        var_d = sum((x - mean_d) ** 2 for x in depeg_history) / len(depeg_history)
        std_d = max(math.sqrt(var_d), 0.01)
        z = (depeg_bps - mean_d) / std_d
        prob = 1.0 / (1.0 + math.exp(-0.5 * (z - 2.0)))
        return round(min(max(prob, 0.0), 1.0), 4)

    def get_alerts(self, health_data: dict) -> list[dict]:
        alerts = []
        for symbol, data in health_data.items():
            if data["status"] == "alert":
                alerts.append({
                    "type": "STABLE_DEPEG_ALERT",
                    "symbol": symbol,
                    "depeg_bps": data["depeg_bps"],
                    "price": data["price"],
                    "ts": data["ts"],
                })
            elif data["status"] == "warning":
                alerts.append({
                    "type": "STABLE_DEPEG_WARNING",
                    "symbol": symbol,
                    "depeg_bps": data["depeg_bps"],
                    "price": data["price"],
                    "ts": data["ts"],
                })
        return alerts
