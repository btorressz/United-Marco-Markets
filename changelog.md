# Changelog

## 2026-02-25 — Fix Paper SELL + Live Pricing + Clean Logs

### Root Cause
Paper SELL was blocked by the risk engine's **300-second cooldown timer**. After any successful order (BUY), all subsequent orders — including sells — were rejected with "Cooldown active: Xs remaining" for 5 minutes. The cooldown was designed for live trading safety but incorrectly applied to paper mode.


## Files Changed

| File | Change |
|------|--------|
| `backend/compute/risk_engine.py` | Added `_is_reducing()` method to detect position-reducing trades. Cooldown now only enforced in live mode. Throttle, leverage, margin, and daily loss checks bypass for position-reducing trades (sells that close/reduce existing longs, buys that close/reduce shorts). Added `execution_mode` parameter to `check_constraints()`. |
| `backend/execution/router.py` | Added live price injection via `PriceAuthority` — orders without explicit price now auto-fill from the Pyth→Kraken→CoinGecko cascade. Added price freshness validation (configurable threshold, default 30s). Stale data blocks live trades, allows paper trades with DEGRADED tag. Integrity WARNING blocks live trades (configurable), tags paper trades. Added `TRADE_BLOCKED_STALE_DATA` and `TRADE_DEGRADED_DATA` event emissions. |
| `backend/execution/paper_exec.py` | Position data now includes `side` field ("long"/"short" derived from signed size). ORDER_SENT and ORDER_FILLED events now include `price_source`, `price_asof_ts`, `data_quality`, and human-readable `message` fields. Return value now includes `side`, `market`, `venue`, `size`. |
| `backend/api/execution_routes.py` | Added explicit side validation (must be "buy" or "sell", returns 400 otherwise). Better error response structure with `status` and `message` fields. |
| `backend/core/event_bus.py` | Added 2 new event types: `TRADE_BLOCKED_STALE_DATA`, `TRADE_DEGRADED_DATA` (total: 61). |
| `backend/config.py` | Added `PRICE_FRESHNESS_THRESHOLD_S` (default 30s) and `PRICE_INTEGRITY_BLOCK_LIVE` (default true) configuration. |
| `backend/logging_config.py` | APScheduler loggers (`apscheduler`, `apscheduler.executors.default`, `apscheduler.scheduler`) set to WARNING level to eliminate noisy "Running job..." messages during trading. |
| `frontend/assets/api.js` | `postJSON()` now parses structured error responses from 403/4xx — extracts `reasons` array or `message` from `detail` for human-readable error display instead of raw JSON. Changed from `console.error` to `console.warn` for API errors (not application crashes). |
| `tests/test_risk_throttle.py` | Updated cooldown test to use `execution_mode="live"`. Added `test_cooldown_skipped_in_paper` and `test_throttle_allows_reducing` tests. |
| `tests/test_paper_trading.py` | **New file** — 21 tests covering: paper BUY creates long, paper SELL creates short, SELL reduces/closes/flips long, BUY closes short, events emitted for both sides, position `side` field, risk engine reducing detection, throttle/daily-loss bypass for reduces, no cooldown in paper mode. |
