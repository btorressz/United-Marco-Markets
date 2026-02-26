import os
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Any

import redis
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


class EventType:
    INDEX_UPDATE = "INDEX_UPDATE"
    SHOCK_SPIKE = "SHOCK_SPIKE"
    DIVERGENCE_ALERT = "DIVERGENCE_ALERT"
    FUNDING_REGIME_FLIP = "FUNDING_REGIME_FLIP"
    RISK_THROTTLE_ON = "RISK_THROTTLE_ON"
    RISK_THROTTLE_OFF = "RISK_THROTTLE_OFF"
    RULE_ACTION_PROPOSED = "RULE_ACTION_PROPOSED"
    ORDER_SENT = "ORDER_SENT"
    ORDER_FILLED = "ORDER_FILLED"
    SWAP_QUOTED = "SWAP_QUOTED"
    SWAP_SENT = "SWAP_SENT"
    ERROR = "ERROR"
    STABLE_DEPEG_ALERT = "STABLE_DEPEG_ALERT"
    STABLE_VOLUME_SPIKE = "STABLE_VOLUME_SPIKE"
    STABLE_FUNDING_SPIKE = "STABLE_FUNDING_SPIKE"
    STABLE_STRESS_ALERT = "STABLE_STRESS_ALERT"
    PEG_BREAK_PROB_UPDATE = "PEG_BREAK_PROB_UPDATE"
    PREDICTION_UPDATE = "PREDICTION_UPDATE"
    PREDICTION_CONFIDENCE_LOW = "PREDICTION_CONFIDENCE_LOW"
    MONTE_CARLO_RUN = "MONTE_CARLO_RUN"
    RISK_VAR_BREACH = "RISK_VAR_BREACH"
    MICROSTRUCTURE_SIGNAL = "MICROSTRUCTURE_SIGNAL"
    DISLOCATION_ALERT = "DISLOCATION_ALERT"
    CARRY_UPDATE = "CARRY_UPDATE"
    CARRY_REGIME_FLIP = "CARRY_REGIME_FLIP"
    AGENT_SIGNAL = "AGENT_SIGNAL"
    AGENT_ACTION_PROPOSED = "AGENT_ACTION_PROPOSED"
    AGENT_BLOCKED = "AGENT_BLOCKED"
    MACRO_TERMINAL_UPDATE = "MACRO_TERMINAL_UPDATE"
    PRICE_DISLOCATION_ALERT = "PRICE_DISLOCATION_ALERT"
    PNL_ATTRIBUTION_UPDATE = "PNL_ATTRIBUTION_UPDATE"
    REGIME_MEMORY_UPDATE = "REGIME_MEMORY_UPDATE"
    EXECUTION_METRICS_UPDATE = "EXECUTION_METRICS_UPDATE"
    SLIPPAGE_ANOMALY_ALERT = "SLIPPAGE_ANOMALY_ALERT"
    SOLANA_CONGESTION_WARNING = "SOLANA_CONGESTION_WARNING"
    JUPITER_ROUTE_RISK = "JUPITER_ROUTE_RISK"
    EXECUTION_THROTTLE = "EXECUTION_THROTTLE"
    FUNDING_ARB_OPPORTUNITY = "FUNDING_ARB_OPPORTUNITY"
    FUNDING_ARB_REGIME_FLIP = "FUNDING_ARB_REGIME_FLIP"
    BASIS_UPDATE = "BASIS_UPDATE"
    BASIS_OPPORTUNITY = "BASIS_OPPORTUNITY"
    BASIS_FEASIBILITY_LOW = "BASIS_FEASIBILITY_LOW"
    LIQUIDITY_THINNING_WARNING = "LIQUIDITY_THINNING_WARNING"
    STABLE_FLOW_UPDATE = "STABLE_FLOW_UPDATE"
    ADAPTIVE_WEIGHTS_UPDATE = "ADAPTIVE_WEIGHTS_UPDATE"
    REGIME_ANALOG_MATCH = "REGIME_ANALOG_MATCH"
    PORTFOLIO_PROPOSAL = "PORTFOLIO_PROPOSAL"
    LIQUIDATION_HEATMAP_UPDATE = "LIQUIDATION_HEATMAP_UPDATE"
    JUPITER_QUOTE_STALE = "JUPITER_QUOTE_STALE"
    JUPITER_SLIPPAGE_SPIKE = "JUPITER_SLIPPAGE_SPIKE"
    HEDGE_PROPOSAL = "HEDGE_PROPOSAL"
    HEDGE_REBALANCE_SUGGESTED = "HEDGE_REBALANCE_SUGGESTED"
    HEDGE_THROTTLE_RECOMMENDED = "HEDGE_THROTTLE_RECOMMENDED"
    SANDBOX_COMPARISON_RUN = "SANDBOX_COMPARISON_RUN"
    REPLAY_COMPLETED = "REPLAY_COMPLETED"
    SLIPPAGE_MODEL_UPDATE = "SLIPPAGE_MODEL_UPDATE"
    SAFE_SIZE_WARNING = "SAFE_SIZE_WARNING"
    HEDGE_RATIO_UPDATE = "HEDGE_RATIO_UPDATE"
    STABLECOIN_PLAYBOOK_TRIGGERED = "STABLECOIN_PLAYBOOK_TRIGGERED"
    TRADE_BLOCKED_STALE_DATA = "TRADE_BLOCKED_STALE_DATA"
    TRADE_DEGRADED_DATA = "TRADE_DEGRADED_DATA"

    ALL = [
        INDEX_UPDATE, SHOCK_SPIKE, DIVERGENCE_ALERT, FUNDING_REGIME_FLIP,
        RISK_THROTTLE_ON, RISK_THROTTLE_OFF, RULE_ACTION_PROPOSED,
        ORDER_SENT, ORDER_FILLED, SWAP_QUOTED, SWAP_SENT, ERROR,
        STABLE_DEPEG_ALERT, STABLE_VOLUME_SPIKE, STABLE_FUNDING_SPIKE,
        STABLE_STRESS_ALERT, PEG_BREAK_PROB_UPDATE,
        PREDICTION_UPDATE, PREDICTION_CONFIDENCE_LOW,
        MONTE_CARLO_RUN, RISK_VAR_BREACH,
        MICROSTRUCTURE_SIGNAL, DISLOCATION_ALERT,
        CARRY_UPDATE, CARRY_REGIME_FLIP,
        AGENT_SIGNAL, AGENT_ACTION_PROPOSED, AGENT_BLOCKED,
        MACRO_TERMINAL_UPDATE, PRICE_DISLOCATION_ALERT,
        PNL_ATTRIBUTION_UPDATE, REGIME_MEMORY_UPDATE,
        EXECUTION_METRICS_UPDATE, SLIPPAGE_ANOMALY_ALERT,
        SOLANA_CONGESTION_WARNING, JUPITER_ROUTE_RISK, EXECUTION_THROTTLE,
        FUNDING_ARB_OPPORTUNITY, FUNDING_ARB_REGIME_FLIP,
        BASIS_UPDATE, BASIS_OPPORTUNITY, BASIS_FEASIBILITY_LOW,
        LIQUIDITY_THINNING_WARNING, STABLE_FLOW_UPDATE,
        ADAPTIVE_WEIGHTS_UPDATE, REGIME_ANALOG_MATCH,
        PORTFOLIO_PROPOSAL, LIQUIDATION_HEATMAP_UPDATE,
        JUPITER_QUOTE_STALE, JUPITER_SLIPPAGE_SPIKE,
        HEDGE_PROPOSAL, HEDGE_REBALANCE_SUGGESTED, HEDGE_THROTTLE_RECOMMENDED,
        SANDBOX_COMPARISON_RUN, REPLAY_COMPLETED,
        SLIPPAGE_MODEL_UPDATE, SAFE_SIZE_WARNING,
        HEDGE_RATIO_UPDATE, STABLECOIN_PLAYBOOK_TRIGGERED,
        TRADE_BLOCKED_STALE_DATA, TRADE_DEGRADED_DATA,
    ]


CHANNEL = "desk:events"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    payload JSONB DEFAULT '{}',
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_events_type ON events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events (ts DESC);
"""


class EventBus:

    def __init__(
        self,
        redis_url: str | None = None,
        database_url: str | None = None,
    ):
        self._redis_url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379")
        self._database_url = database_url or os.environ.get("DATABASE_URL", "")
        self._redis: redis.Redis | None = None
        self._table_ensured = False

    def _get_redis(self) -> redis.Redis | None:
        if self._redis is not None:
            return self._redis
        try:
            self._redis = redis.Redis.from_url(self._redis_url, decode_responses=True)
            self._redis.ping()
            return self._redis
        except Exception:
            logger.warning("Redis unavailable at %s, pubsub disabled", self._redis_url)
            self._redis = None
            return None

    def _get_pg_conn(self):
        if not self._database_url:
            return None
        try:
            conn = psycopg2.connect(self._database_url)
            conn.autocommit = True
            return conn
        except Exception:
            logger.warning("Postgres unavailable, event persistence disabled", exc_info=True)
            return None

    def _ensure_table(self) -> None:
        if self._table_ensured:
            return
        conn = self._get_pg_conn()
        if conn is None:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(_CREATE_TABLE_SQL)
            self._table_ensured = True
        except Exception:
            logger.warning("Failed to ensure events table", exc_info=True)
        finally:
            conn.close()

    def emit(self, event_type: str, source: str, payload: dict[str, Any] | None = None) -> str:
        event_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        payload = payload or {}

        event_data = {
            "id": event_id,
            "event_type": event_type,
            "source": source,
            "payload": payload,
            "ts": now.isoformat(),
        }

        r = self._get_redis()
        if r is not None:
            try:
                r.publish(CHANNEL, json.dumps(event_data, default=str))
            except Exception:
                logger.warning("Failed to publish event to Redis", exc_info=True)

        self._ensure_table()
        conn = self._get_pg_conn()
        if conn is not None:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO events (id, event_type, source, payload, ts) VALUES (%s, %s, %s, %s, %s)",
                        (event_id, event_type, source, json.dumps(payload, default=str), now),
                    )
            except Exception:
                logger.warning("Failed to persist event to Postgres", exc_info=True)
            finally:
                conn.close()

        logger.info("Event emitted: %s from %s [%s]", event_type, source, event_id)
        return event_id

    def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        self._ensure_table()
        conn = self._get_pg_conn()
        if conn is None:
            return []
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, event_type, source, payload, ts FROM events ORDER BY ts DESC LIMIT %s",
                    (limit,),
                )
                rows = cur.fetchall()
                results = []
                for row in rows:
                    entry = dict(row)
                    if isinstance(entry.get("ts"), datetime):
                        entry["ts"] = entry["ts"].isoformat()
                    if isinstance(entry.get("payload"), str):
                        try:
                            entry["payload"] = json.loads(entry["payload"])
                        except (json.JSONDecodeError, TypeError):
                            pass
                    results.append(entry)
                return results
        except Exception:
            logger.warning("Failed to fetch recent events", exc_info=True)
            return []
        finally:
            conn.close()
