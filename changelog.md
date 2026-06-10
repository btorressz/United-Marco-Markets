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


## How Live Pricing Freshness/Integrity Is Enforced

Before every trade:
1. The router fetches the latest price from the authority cascade (Pyth → Kraken → CoinGecko)
2. If no price data exists and no explicit price was provided: trade blocked with clean message
3. Price freshness checked against `PRICE_FRESHNESS_THRESHOLD_S` (default 30s):
   - **Live mode**: stale data blocks the trade, emits `TRADE_BLOCKED_STALE_DATA`
   - **Paper mode**: allows trade but tags with `data_quality: DEGRADED`, emits `TRADE_DEGRADED_DATA`
4. Price integrity checked (cross-venue deviation):
   - **Live mode**: WARNING status blocks trade (configurable via `PRICE_INTEGRITY_BLOCK_LIVE`)
   - **Paper mode**: allows trade with DEGRADED tag
5. Every trade event includes: `price_asof_ts`, `price_source`, `integrity_status`, `data_age_ms`, `tariff_ts`, `shock_ts`

### Logging Changes
- APScheduler loggers set to WARNING level (was INFO)
- No more "Running job Kraken Price Ingest..." noise during trade actions
- Application trade logs (ORDER_SENT, ORDER_FILLED) remain at INFO level
- Risk warnings and errors remain visible

### Paper SELL Behavior Rules
- `side: "sell"` opens a short position if no existing position
- `side: "sell"` reduces an existing long position
- `side: "sell"` closes an existing long if size matches exactly
- `side: "sell"` flips from long to short if sell size exceeds long size
- Reducing/closing trades bypass: cooldown, throttle, leverage limit, margin limit, daily loss limit
- New short-opening sells are subject to all risk checks

### Test Results
98 tests passing (77 original + 21 new):
- `test_index_calc.py`: 6 passed
- `test_shock_calc.py`: 16 passed
- `test_divergence_alerts.py`: 14 passed
- `test_risk_throttle.py`: 18 passed (was 16, added 2)
- `test_new_features.py`: 25 passed
- `test_paper_trading.py`: 19 passed (new file)
