# Tariff Risk Desk — Codebase Guide

> **Current state:** 145 tests passing · 31 API routers · 31 compute modules · 7 agents · 7 ingest sources · Phase 6 complete

---

## Root

| File | Purpose |
|------|---------|
| `main.py` | Entry point. Starts Redis (if available), creates the FastAPI app, mounts static files at `/frontend`, applies database migrations, launches the APScheduler with periodic ingest jobs, and runs Uvicorn on port 5000. Registers all 31 API routers. Serves `frontend/index.html` at root `/` with no-cache headers. |
| `replit.md` | Project metadata and architecture notes kept in sync. Always loaded into agent memory. |
| `codebase.md` | This file — detailed technical guide to every file in the codebase. |
| `summary.md` | Plain-English description for non-technical readers. |
| `changelog.md` | Feature changelog by phase. |
| `explanation.md` | Extended architectural explanation. |

---

## Backend (`backend/`)

Organized into eight packages: `api`, `core`, `compute`, `agents`, `ml`, `ingest`, `execution`, and `data`.

### `backend/config.py`

Centralized configuration from environment variables with safe defaults:
- Execution mode (`EXECUTION_MODE`, default: `paper`)
- Risk limits (`MAX_LEVERAGE=3.0`, `MAX_MARGIN_USAGE=0.6`, `MAX_DAILY_LOSS=500`)
- Price freshness (`PRICE_FRESHNESS_THRESHOLD_S=30`)
- Integrity enforcement (`PRICE_INTEGRITY_BLOCK_LIVE`, default: `false`)
- WITS country list for tariff data
- API keys for Hyperliquid, Solana/Drift/Jupiter (all optional — fail-open)
- Adaptive weights toggle (`ADAPTIVE_WEIGHTS`, default: `1`)

### `backend/logging_config.py`

Structured JSON logging across the entire application. All entries include ISO-8601 timestamp, level, logger name, and message. APScheduler, urllib3, httpx, redis loggers silenced to WARNING. Trade logs (ORDER_SENT, ORDER_FILLED) remain at INFO.

---

### `backend/api/` — HTTP & WebSocket Routes

31 route files, all registered in `main.py`. Every router is self-contained with fail-open error handling.

| File | Prefix | Endpoints | What it does |
|------|--------|-----------|--------------|
| `index_routes.py` | `/api/index` | `/latest`, `/history`, `/components`, `/alerts`, `/macro-terminal` | Tariff Pressure Index current value, history (window: 1h/4h/1d/7d), components breakdown, and the Macro Terminal returning WITS tariff series, rolling delta, country weights, and correlation heatmap. |
| `markets_routes.py` | `/api/markets` | `/latest`, `/funding`, `/integrity` | Multi-venue SOL/BTC/ETH prices from Pyth, Kraken, CoinGecko, Hyperliquid, and Drift. Funding rates and cross-venue price integrity (deviations in bps). |
| `divergence_routes.py` | `/api/divergence` | `/spreads`, `/alerts` | Cross-venue spread analysis — detects when the same asset trades at different prices across venues. Returns spread bps and dislocation alerts. |
| `stablecoin_routes.py` | `/api/stablecoins` | `/health`, `/history`, `/alerts` | Stablecoin peg monitor for USDC, USDT, DAI. Health, stress, peg-break probability, depeg heatmap. |
| `predict_routes.py` | `/api/predict` | `/latest` | 7-feature sigmoid macro prediction — probability of BTC up in 4h with confidence and driver explanations. |
| `montecarlo_routes.py` | `/api/montecarlo` | `/run` | Monte Carlo VaR/CVaR simulation. Accepts symbol, position size, horizon (float hours), N paths (100–10,000). Returns VaR/CVaR at 95%, mean PnL, distribution histogram. |
| `yield_routes.py` | `/api/yield` | `/carry` | Annualized carry scores from funding rates across venues. |
| `microstructure_routes.py` | `/api/microstructure` | `/latest` | OB imbalance (buy/sell pressure), basis spread, bid-ask spread from Hyperliquid. |
| `agents_routes.py` | `/api/agents` | `/signals`, `/registry` | Runs all 7 registered agents against current state. Returns structured signals with confidence, severity, direction, proposed action, reasoning, and data timestamp. |
| `rules_routes.py` | `/api/rules` | `/evaluation`, `/status`, `/adaptive-weights` | Evaluates 5-rule strategy engine against current market state. Returns triggered actions. Adaptive weights endpoint returns dynamic weight adjustments. |
| `execution_routes.py` | `/api/execution` | `/order`, `/positions`, `/trades`, `/pnl` | Order submission (through ExecutionRouter with risk checks), position listing (live + DB), paper trade history, PnL attribution. |
| `risk_routes.py` | `/api/risk` | `/status`, `/guardrails`, `/stress`, `/regime-analogs` | Risk guardrail status, 4-scenario stress tests, and regime analog outcome distribution. |
| `events_routes.py` | `/api/events` | `/` | Paginated event timeline from Postgres. Default limit 50, newest first. |
| `health_routes.py` | `/api/health` | `/`, `/feeds`, `/redis` | System health (DB, Redis, scheduler, version). Feed status for all 7 data sources (Pyth, Kraken, CoinGecko, Hyperliquid, Drift, WITS, GDELT) with per-feed age, status, and authority flag. Redis health with ping latency, memory usage, key count, and fallback mode flag. |
| `ws_routes.py` | `/ws/live` | WebSocket | Real-time event stream. Subscribes to Redis `desk:events` pub/sub, forwards events to all connected clients. Sends snapshot on connect. |
| `metrics_routes.py` | `/api/metrics` | `/eqi` | Execution Quality Index — composite score (0–100), latency p50/p95, avg slippage bps, fill count, anomaly list. |
| `solana_routes.py` | `/api/solana` | `/quality` | Solana execution quality score, congestion detection, slippage risk, route depth. |
| `funding_arb_routes.py` | `/api/funding-arb` | `/latest` | HL vs Drift funding arb — spread bps, persistence, arb signal direction, expected net carry. |
| `basis_routes.py` | `/api/basis` | `/latest` | Perpetual basis monitor — HL/Kraken, Drift/Pyth, HL/Drift spreads with annualized bps and feasibility. |
| `stable_flow_routes.py` | `/api/stable-flow` | `/latest` | Stablecoin flow momentum and risk-on/off indicator. |
| `portfolio_routes.py` | `/api/portfolio` | `/proposal` | Portfolio construction (risk_parity / mean_variance / kelly). Proposals only — never auto-trades. |
| `liquidation_routes.py` | `/api/liquidation` | `/heatmap` | Leverage (1x–10x) vs price-drop (5%–50%) liquidation probability grid. |
| `sandbox_routes.py` | `/api/sandbox` | `/run`, `/latest`, `/history` | Strategy A/B comparison — evaluates two rule configurations against the same market snapshot. |
| `replay_routes.py` | `/api/replay` | `/run`, `/latest` | Event replay engine — deterministic backtesting through the historical event log. |
| `slippage_routes.py` | `/api/slippage` | `/latest`, `/estimate` | Slippage curves and max safe order sizes across Hyperliquid, Jupiter, Drift. |
| `hedge_routes.py` | `/api/hedge` | `/latest`, `/correlations` | Hedge ratio analysis — rolling correlation, OLS beta, effectiveness (R²), best pair, and recommended ratio. |
| `allocation_routes.py` | `/api/allocation` | `/latest`, `/rebalance-preview` | **[Phase 6]** Risk-weighted capital allocation across 5 venues (Hyperliquid, Drift, Jupiter Spot, Stablecoins, Cash). Returns weights summing to 1.0, caps, floors, risk-adjusted expected returns, confidence, reasoning. Rebalance preview shows diff from current to proposed. |
| `ml_routes.py` | `/api/ml` | `/features/latest`, `/prediction/latest`, `/train/offline`, `/training/history` | **[Phase 6]** ML feature store + inference. Latest 15-feature vector, heuristic-or-trained prediction (probability, confidence, model_type, top drivers), offline training endpoint (POST samples+labels), training run history. |
| `backtest_routes.py` | `/api/backtest` | `/run`, `/latest`, `/history` | **[Phase 6]** Historical backtest. POST config (strategy, window_days, capital, venue, fee_bps, slippage_bps) → returns total return, Sharpe, max drawdown, win rate, trade count, avg slippage, VaR/CVaR, equity curve, per-strategy PnL. Deterministic (seeded RNG). Emits BACKTEST_STARTED/COMPLETED events. |
| `volatility_routes.py` | `/api/volatility` | `/regime`, `/recommendations` | **[Phase 6]** Volatility regime classification (5 regimes) with per-regime scores and confidence. Recommendations: leverage adjustment, slippage tolerance, hedge aggressiveness, execution style, strategy weight shifts. |
| `portfolio_risk_routes.py` | `/api/portfolio-risk` | `/summary`, `/contributions`, `/exposures` | **[Phase 6]** Real-time portfolio risk metrics from open positions. Total/long/short/net exposure, VaR/CVaR, max/current drawdown, concentration risk by venue and asset, per-venue exposure table, warnings list. Per-position risk contributions and exposure breakdown. |

---

### `backend/core/` — Shared Infrastructure

| File | What it does |
|------|--------------|
| `models.py` | Pydantic models for internal data: `PriceTick`, `FundingTick`, `DivergenceAlert`, and others. Type safety across all components. |
| `schemas.py` | Pydantic response models for API responses: `IndexLatestResponse`, `RuleActionResponse`, `AlertResponse`, `StressTestResult`, `MonteCarloResult`, etc. |
| `event_bus.py` | Unified event system with **85 defined event types**. Emits to Redis pub/sub (`desk:events`) for WebSocket broadcast and Postgres for persistence. All components write through one bus. Key event types grouped by domain: index/shock updates, trade lifecycle, risk/throttle, agent signals, ML/backtest/allocation, regime/vol, Redis health. |
| `state_store.py` | Redis-backed snapshot store with in-memory fallback (fail-open). Components write keyed snapshots with configurable TTLs. Also provides throttle checking — prevents duplicate alerts. Key namespaces: `price:*`, `index:*`, `desk:*`, `regime:*`, `market:*`. |
| `price_authority.py` | Pyth → Kraken → CoinGecko cascade. Returns best available price with source attribution. Fails gracefully. |
| `price_validator.py` | Cross-venue price integrity checker. Computes pairwise deviations in bps. Flags WARNING at >50bps threshold. Emits throttled `PRICE_DISLOCATION_ALERT`. Returns OK/WARNING/CRITICAL. |
| `normalization.py` | Normalizes raw data from Pyth, Kraken, CoinGecko, Hyperliquid, and Drift into consistent internal formats. |
| `timeutils.py` | UTC helpers and window-string parsing (1h/4h/1d/7d → seconds). |

---

### `backend/compute/` — Pure Computation Modules (31 modules)

Stateless — take data in, return results. No I/O, no side effects.

| File | What it computes |
|------|-----------------|
| `index_calc.py` | **Tariff Pressure Index** — weighted composite (0–100) from WITS tariff rates, trade values, and GDELT news shock. Country weights scale by trading-partner size. |
| `shock_calc.py` | **GDELT Shock Score** — z-score of news tone + volume. Detects geopolitical shock spikes above historical norms. |
| `divergence.py` | **Cross-venue spread detection** — spread in bps per venue pair, severity classification, dislocation alerts above threshold. |
| `regime.py` | **Regime classification** — funding regime (positive/negative/neutral) and volatility regime (low/normal/high/extreme) from rate magnitude and price volatility. |
| `regime_memory.py` | **Regime persistence + analog library** — stores regime state transitions; `get_outcome_distribution()` returns avg returns at 4h/24h/3d horizons, win rates, and best historical analog for current regime pattern. |
| `carry_score.py` | **Annualized carry** — converts 8h periodic funding rates to annualized carry scores for cross-venue comparison. |
| `rules_engine.py` | **5 configurable rules**: tariff shock hedge, divergence arb, funding flip, vol regime scale, stable rotation. Each returns proposed action with venue, market, side, size, reason. |
| `risk_engine.py` | **Risk guardian** — enforces leverage (3x), margin (60%), daily loss ($500) limits. Detects position-reducing trades via `_is_reducing()` — reduces bypass all constraints. Cooldown only in live mode. |
| `stress_tests.py` | **4 stress scenarios** — tariff escalation, liquidity crisis, flash crash, funding flip. Returns PnL impact, max drawdown, margin call flag, per-position breakdown. |
| `stablecoin_health.py` | **Peg monitor** — depeg magnitude in bps, peg status classification, stress detection, peg-break probability from multi-signal composite. |
| `macro_predictor.py` | **Sigmoid macro prediction** — 7-feature logistic model. Returns P(BTC up in 4h), confidence, driver explanations. |
| `monte_carlo.py` | **Monte Carlo engine** — GBM paths (up to 10,000), VaR/CVaR at 95%, mean PnL, distribution histogram. Supports sub-hour horizons (float hours). |
| `microstructure.py` | **Orderbook microstructure** — bid/ask imbalance, basis, effective spread, liquidity depth from Hyperliquid data. |
| `stable_yield.py` | **Stablecoin yield** — lending rates, LP yields, funding carry across stablecoin pairs. |
| `pnl_attribution.py` | **PnL decomposition** — market move, funding paid/received, fees, slippage. Per-position and aggregate. |
| `execution_metrics.py` | **Execution Quality Index** — rolling window of last 100 fills. Latency p50/p95, avg slippage bps, anomaly detection via z-score (>2σ). Composite EQI score 0–100. |
| `solana_liquidity.py` | **Solana execution quality** — 4-component score (spread, slippage, congestion, route complexity). Congestion via RPC latency + slot delta. Returns quality score (0–100), congestion flag, slippage risk level. |
| `funding_arb.py` | **Funding arb detector** — HL vs Drift spread in bps, persistence tracking, rolling 100-entry mean. Signal: long_hl_short_drift / short_hl_long_drift / none. |
| `basis_engine.py` | **Perp basis monitor** — HL/Kraken, Drift/Pyth, HL/Drift spreads. Annualized bps, net carry, execution feasibility (0–100). 200-entry rolling history. |
| `stable_flow.py` | **Stablecoin flow momentum** — dominance proxy + depeg stress → momentum (−1 to +1), risk-on/off indicator, driver explanations. |
| `adaptive_weights.py` | **Dynamic risk weights** — adjusts four predictor weights (macro, carry, microstructure, momentum) based on shock level, vol, and funding regime. Equal default (25% each). |
| `portfolio_optimizer.py` | **Portfolio construction** — risk_parity, mean_variance, scaled Kelly across hl_perps/drift_perps/spot_jupiter/stablecoins. Hard caps + floors. Proposals only. |
| `liquidation_heatmap.py` | **Liquidation heatmap** — 6×8 leverage/price-drop grid. Probability from margin distance, vol-adjusted factor, margin usage. Monotonicity enforced across both axes. |
| `strategy_sandbox.py` | **Strategy A/B comparison** — evaluates two rule configs against the same market snapshot. Monte Carlo VaR per variant. Recommends best variant. |
| `replay_engine.py` | **Event replay** — deterministic chronological replay of historical events through RulesEngine. Returns action log, final portfolio value, max drawdown. |
| `slippage_model.py` | **Slippage curves** — order-size vs bps curves for size buckets ($100–$100k). Max safe sizes at 10/25/50bps thresholds. Multi-venue (HL/Jupiter/Drift). |
| `hedge_ratio.py` | **Hedge ratio calculator** — Pearson correlation, OLS beta, hedge ratio, effectiveness (R²) over configurable observation window. Best pair, recommended ratio, macro-correlation overlay. |
| `stablecoin_playbook.py` | **Depeg playbook** — 5-tier action ladder (monitor → reduce → diversify → hedge → emergency_exit) based on depeg magnitude and peg-break probability. |
| `capital_allocator.py` | **[Phase 6] Capital allocation engine** — risk-weighted allocation across 5 venues: Hyperliquid, Drift, Jupiter Spot, Stablecoins, Cash. Reads live state (tariff shock, vol regime, stable health, funding arb, basis, exec quality). Applies caps (40%/30%/30%/70%/100%) and floors (5%/3%/3%/10%/5%). Weights sum to exactly 1.0. Returns confidence (0–1) and reasoning array. Proposal-only — never auto-trades. |
| `vol_regime_engine.py` | **[Phase 6] Volatility regime classifier** — 5 regimes: low_volatility, normal_volatility, high_volatility, shock_regime, liquidity_crunch. Computes per-regime score from annualized vol, shock score, tariff index, stable health, orderbook depth, exec quality. Returns regime, confidence, all scores, inputs, and per-regime recommendations (leverage adjustment, slippage tolerance, hedge aggressiveness, execution style). |
| `backtester.py` | **[Phase 6] Historical backtester** — deterministic simulation with seeded RNG (no live data required). Supports strategies: momentum, carry_arb, buy_hold. Simulates N trading days, applies fee + slippage model, tracks equity curve, computes Sharpe ratio, max drawdown (`_compute_max_drawdown`), win rate, VaR/CVaR (`_compute_var_cvar`), per-strategy PnL breakdown. Config echoed in result. Result cached to Redis with TTL. |

---

### `backend/ml/` — ML Feature Store & Training Scaffold (Phase 6)

| File | What it does |
|------|--------------|
| `feature_store.py` | Builds a 15-feature vector from live state snapshots. Features: `tariff_index`, `tariff_delta`, `shock_score`, `shock_abs`, `funding_skew`, `basis_spread`, `vol_regime_encoded`, `stable_health`, `stable_flow`, `divergence_score`, `orderbook_imbalance`, `liquidity_score`, `slippage_score`, `exec_quality`, `predictor_conf`. Missing data handled with safe defaults. Returns feature dict, ordered feature names, quality report (`all_present`, `stale_fields`), and `features_to_vector()` converter. |
| `training.py` | Offline-only training scaffold. Supports logistic regression (scikit-learn) and optional LightGBM. Requires `MIN_SAMPLES` (default 20) to train. Returns `success`, `method`, `accuracy`, `n_samples`, `reason` (on failure), `ts`. Stores trained model in module-level `_TRAINED_MODEL` for inference. Heuristic fallback always active. |
| `inference.py` | Prediction endpoint. Uses trained model if available, else `_heuristic_predict()` which scores from `tariff_index`, `shock_score`, `stable_health`, `predictor_conf`. Returns `probability` (0–1), `prediction` (0/1), `confidence` (0–1), `model_type` (`heuristic_fallback` or `logistic`/`lightgbm`), `ts`. |
| `explainability.py` | Feature importance and SHAP-based explanations. Returns top drivers with feature name, description, contribution value, and direction. SHAP is optional (fail-open if unavailable). Falls back to coefficient-based importance for logistic regression. |
| `__init__.py` | Package marker. |

---

### `backend/agents/` — Heuristic AI Agents (7 agents)

All agents follow the same interface: `evaluate(state: dict) -> list[dict]`. Each signal contains: `agent`, `signal`, `confidence` (0–1), `severity` (low/medium/high), `direction` (bullish/bearish/neutral), `proposed_action`, `reason`, `ts`, `data_ts_used`. Deterministic, explainable, no ML models.

| File | Agent | Monitors | Confidence range |
|------|-------|----------|-----------------|
| `risk_agent.py` | Risk Agent | Liquidation distance, margin usage, throttle conditions (high shock + high vol). Proposes `reduce_size` or `block_execution`. | 0.75–0.90 |
| `macro_agent.py` | Macro Agent | Tariff momentum acceleration, GDELT shock spikes (>0.5), high tariff regime (>60). Proposes `reduce_exposure` or `hedge`. | 0.70–0.85 |
| `execution_agent.py` | Execution Agent | Pre-trade safety: spread width, liquidity depth, price integrity. Warns on high slippage (>20bps), wide spreads. Can `block_execution` in live mode. | 0.75–0.90 |
| `liquidity_agent.py` | Liquidity Agent | Stablecoin depeg (>50bps), OB imbalance (>0.7), thin liquidity. Proposes `reduce_size` or `pause_trading`. | 0.70–0.85 |
| `hyperliquid_agent.py` | Hyperliquid Agent | HL-specific microstructure: OB imbalance direction, spread compression, trade aggression, liquidity thinning. Emits `MICROSTRUCTURE_SIGNAL`, `LIQUIDITY_THINNING_WARNING`. | 0.70–0.90 |
| `jupiter_agent.py` | Jupiter Agent | Jupiter/Solana swap intelligence: quote freshness (>30s stale), route complexity (warns >3 hops), price impact (warns >1%), slippage risk, Solana congestion (RPC latency, slot lag). Reuses `solana_liquidity.py`. Emits `JUPITER_QUOTE_STALE`, `JUPITER_SLIPPAGE_SPIKE`. | 0.70–0.95 |
| `hedging_agent.py` | Hedging Agent | Position-aware hedge recommendations. Urgency score from shock, vol, funding, margin usage. Proposes reduce_exposure, add_hedge, rotate_to_stables, or increase_size. Returns per-position actions with urgency scores and suggested hedge ratios. | 0.70–0.90 |

---

### `backend/ingest/` — Data Ingestion (7 sources)

APScheduler-driven periodic jobs. All fail-open — errors logged as WARNING, never crash.

| File | Source | What it fetches | Frequency |
|------|--------|----------------|-----------|
| `wits_ingest.py` | World Bank WITS | Tariff rates by country pair, trade values | 60 min |
| `gdelt_ingest.py` | GDELT Project | News tone/volume for trade-policy keywords | 5 min |
| `kraken_ingest.py` | Kraken | Spot prices BTC/SOL/ETH | 30 s |
| `coingecko_ingest.py` | CoinGecko | Prices + market cap, fallback source | 60 s |
| `pyth_ingest.py` | Pyth Network | Oracle prices (primary authority) | 10 s |
| `hyperliquid_ws.py` | Hyperliquid | Perp prices, OB data, funding via WebSocket | Real-time |
| `drift_ingest.py` | Drift Protocol | SOL-PERP prices, funding rates | 60 s |
| `scheduler.py` | — | APScheduler setup, registers all ingest jobs | — |

---

### `backend/execution/` — Trade Execution

| File | What it does |
|------|--------------|
| `router.py` | **ExecutionRouter** — central trade dispatcher. Applies risk checks before routing. Selects executor by venue (paper/hyperliquid/drift/jupiter). In paper mode: all trades go to PaperExecutor. Injects live price from Pyth→Kraken→CoinGecko cascade when price omitted. Checks freshness (`PRICE_FRESHNESS_THRESHOLD_S`) — stale blocks live, tags paper as DEGRADED. Emits TRADE_BLOCKED_STALE_DATA or TRADE_DEGRADED_DATA events. |
| `paper_exec.py` | **PaperExecutor** — simulated execution engine. Handles open (new position), close (full exit), reduce (partial), and flip (direction reversal) for both longs and shorts. Persists to Postgres and Redis. Emits ORDER_SENT → ORDER_FILLED events. No cooldown in paper mode. |
| `hyperliquid_exec.py` | **HyperliquidExecutor** — live execution via Hyperliquid API. Requires `HYPERLIQUID_PRIVATE_KEY`. Constructs and signs orders, handles partial fills and errors gracefully. |
| `drift_exec.py` | **DriftExecutor** — Drift Protocol execution. Disabled if no Solana key. |
| `jupiter_exec.py` | **JupiterExecutor** — Jupiter swap aggregator execution. Disabled if no `SOLANA_PRIVATE_KEY`. Quotes route, checks price impact, executes swap. |
| `solana_tx.py` | Solana transaction helpers — keypair loading, serialization, submission to RPC. |

---

### `backend/data/` — Database Layer

| File | What it does |
|------|--------------|
| `db.py` | PostgreSQL connection pool via psycopg2. Schema initialization: creates `index_snapshots`, `events`, `market_ticks`, `positions` tables with indexes. Connection retry with backoff. |
| `repositories/index_repo.py` | Index snapshot read/write — latest value and time-windowed history. |
| `repositories/market_repo.py` | Market tick persistence and time-windowed queries. |
| `repositories/events_repo.py` | Event log read/write with pagination. |
| `repositories/positions_repo.py` | Position CRUD — open, close, update, list all. |

---

## Frontend (`frontend/`)

Single-page application. No React, no build step. Vanilla HTML + CSS + JS + Chart.js.

### `frontend/index.html`

615 lines. 8-tab dashboard with all panel containers. Key structure:

**Header** — title, DB indicator, price integrity badge, auto-refresh toggle (AUTO/PAUSED), light/dark theme toggle (persists to localStorage), WebSocket connection status badge.

**Navigation** — 8 tab buttons: Index, Markets, Divergence, Stablecoins, Strategy, Execution, Risk, Agents.

**Index tab** — Tariff Index, Shock Score, Rate of Change, Last Updated metrics. Index & Shock History chart with `1h/4h/1d/7d` timeframe buttons and LIVE freshness badge. Components table (left), Prediction panel (right). Macro Terminal: WITS series, Rolling delta, Country weights, Correlation heatmap (2×2 grid).

**Markets tab** — Live prices table with markets-freshness badge. Funding chart + Carry panel (grid-2). Microstructure cards (OB imbalance, Basis, Price Integrity). Solana Execution Quality cards. Funding Arb panel. Basis Monitor panel. Collapsible Feed Status panel (toggle button shows/hides).

**Divergence tab** — Spread bar chart with timeframe selector. Spreads table. Dislocation alerts list.

**Stablecoins tab** — Peg monitor boxes (USDC/USDT/DAI). Depeg heatmap table. Stress panel. Alerts list. Stable flow panel.

**Strategy tab** — Active rule signals. Registered rules list. Adaptive Risk Weights panel. Portfolio Proposal panel. **Capital Allocation panel** (venue weight bars, confidence, RAR, reasoning). **ML Signal Layer panel** (BTC up probability, confidence, feature driver bars). **Historical Backtest** (inline form: strategy/window/capital/venue/fees + submit → results panel with equity curve SVG).

**Execution tab** — Decision Data Status panel (integrity/freshness pre-trade check, paper mode annotation). Order form (venue, market, side, size, price, submit with risk-check feedback). Positions table. Trades table. EQI panel.

**Risk tab** — Throttle banner (active/inactive). **Portfolio Risk Dashboard** (exposure breakdown, VaR/CVaR, concentration risk, venue exposure table). **Volatility Regime panel** (5-regime bar chart, current regime badge, recommendations). Leverage/Margin/PnL metric row. Guardrails panel. Stress test form (4 scenarios) + result. Monte Carlo form (symbol, size, horizon + time unit selector: minutes/hours/days, paths) + result + distribution chart. Regime Replay panel. Liquidation Heatmap table.

**Agents tab** — Status row (agent count, signal count, last updated). Agent Signals list (expandable reasoning). Agent Registry cards.

**Event Timeline** — always-visible bottom panel, last 50 events, color-coded by type (fill/trade/alert/error/info).

---

### `frontend/assets/styles.css`

~1,170 lines. CSS custom properties with two themes:

```css
:root { /* dark — default */ }
[data-theme="light"] { /* light overrides */ }
```

Key component classes: `.header`, `.tab-nav`, `.tab-btn`, `.tab-panel`, `.card`, `.card-header`, `.metric-row`, `.metric-box`, `.metric-value`, `.badge` (badge-green/red/blue/yellow/purple), `.freshness-badge` (live/fresh/stale/degraded/nodata), `.timeframe-selector`, `.tf-btn`, `.inline-form`, `.form-group`, `.form-label`, `.form-input`, `.form-select`, `.btn`, `.btn-primary`, `.throttle-banner`, `.rule-card`, `.agent-signal-card`, `.agent-signal-reason-detail` (collapsible), `.guardrail-row`, `.alert-item`, `.timeline-panel`, `.timeline-body`, `.auto-refresh-toggle`, `.theme-toggle`, `.integrity-badge`, `.status-badge`, `.section-header`, `.section-title`, `.empty-state`, `.table-scroll`, `.chart-container`, `.grid-2`, `.grid-3`.

---

### `frontend/assets/api.js`

~130 lines. All REST API methods as a single `API` module. Two helpers: `fetchJSON(path)` (GET with error handling) and `postJSON(path, body)` (POST). ~50 endpoint methods organized by domain. Phase 6 additions: `getAllocationLatest`, `postRebalancePreview`, `getMLFeaturesLatest`, `getMLPredictionLatest`, `postMLTrainOffline`, `getMLTrainingHistory`, `postBacktestRun`, `getBacktestLatest`, `getBacktestHistory`, `getVolRegime`, `getVolRecommendations`, `getPortfolioRiskSummary`, `getPortfolioRiskContributions`, `getPortfolioRiskExposures`, `getRedisHealth`.

---

### `frontend/assets/ui.js`

~1,265 lines. All render functions as a single `UI` module. Every function guards against null data and missing DOM elements. Key functions:

| Function | Renders |
|----------|---------|
| `renderIndexTab(data)` | Index metrics, chart, components, prediction, macro terminal (calls `renderMacroTerminal`) |
| `renderMacroTerminal(mt)` | WITS series table, rolling delta bar chart, country weights bars, correlation heatmap grid |
| `renderMarketsTab(data)` | Prices table, funding chart, carry panel, microstructure cards, Solana quality, funding arb, basis, feed status |
| `renderDivergenceTab(data)` | Spread bar chart, spreads table, dislocation alerts |
| `renderStablecoinsTab(data)` | Peg monitor boxes, depeg heatmap, stress panel, alerts, stable flow |
| `renderStrategyTab(data)` | Rule signals, rules list, adaptive weights, portfolio proposal; calls `renderAllocationPanel`, `renderMLPanel`, `renderBacktestPanel` |
| `renderExecutionTab(data)` | Positions table, trades table, EQI panel |
| `renderDecisionDataPanel(data)` | Pre-trade data status (integrity, freshness, mode warning) |
| `renderRiskTab(data)` | Throttle banner, metrics, guardrails, stress result, MC result, liquidation heatmap, regime replay; calls `renderPortfolioRiskPanel`, `renderVolRegimePanel` |
| `renderAgentsTab(data)` | Agent signal cards (with collapsible reasoning), registry cards |
| `renderFeedStatus(data)` | Feed status table with age, status badges, authority flag |
| `renderAllocationPanel(data)` | **[Phase 6]** Animated venue weight bars, RAR annotations, confidence badge, collapsible reasoning |
| `renderMLPanel(data)` | **[Phase 6]** BTC up probability, confidence, model type, feature driver bars |
| `renderBacktestPanel(data)` | **[Phase 6]** Metrics grid (return/Sharpe/drawdown/win rate/trades/slippage/VaR/CVaR), config summary, per-strategy PnL, SVG equity curve |
| `renderVolRegimePanel(volRegime, volRecs)` | **[Phase 6]** Regime badge, per-regime score bars, recommendations card |
| `renderPortfolioRiskPanel(data)` | **[Phase 6]** Exposure metrics, VaR/CVaR, concentration risk, venue exposure table, warnings |
| `renderRedisHealth(data)` | **[Phase 6]** Redis connection status, ping latency, memory, key count, fallback mode flag |
| `renderFreshnessBadge(id, ts)` | LIVE/FRESH/STALE/DEGRADED/NO DATA badge with age |
| `renderTimeline(events)` | Event timeline rows — color-coded by type |
| `addEventToTimeline(event, isNew)` | Prepends single event to timeline (called by WS flush) |
| `updateConnectionStatus(connected)` | Header WS status badge |

---

### `frontend/assets/app.js`

~490 lines. Main orchestrator as `App` module. Key responsibilities:

**Init sequence** — `initTheme` (localStorage, toggle button, re-themes charts) → `initTabs` → `initCharts` → `initWebSocket` → `initOrderForm` → `initStressTestForm` → `initMCForm` → `initBacktestForm` → `initFeedStatusToggle` → `initAutoRefreshToggle` → `initTimeframeSelectors` → `initVisibilityListener` → first `refresh()` → 5s polling interval.

**Tab refresh functions** — `refreshIndex`, `refreshMarkets`, `refreshDivergence`, `refreshStablecoins`, `refreshStrategy` (now includes allocation + ML prediction), `refreshExecution`, `refreshRisk` (now includes portfolio risk + vol regime + recommendations), `refreshAgents`. Each uses `Promise.allSettled` — partial data still renders.

**Form handlers:**
- `initBacktestForm` — captures strategy/window/capital/venue/fees, calls `API.postBacktestRun`, renders result + adds BACKTEST_COMPLETED event to timeline. Button disables during run, re-enables on completion or error.
- `initMCForm` — captures symbol/size/horizon_value/horizon_unit/paths, calls `convertHorizonToHours(value, unit)` (minutes÷60, hours×1, days×24), runs MC, shows human-readable summary ("Horizon: 15 minutes").
- `initStressTestForm` — runs stress test scenario, renders result in Risk tab.
- `initOrderForm` — submits order via `API.postOrder`, shows feedback.

**Performance features:**
- `wsMessageBuffer` + `wsFlushTimer` — batches WS messages, flushes every 50ms.
- `tabVisible` flag — visibility change listener pauses polling when tab hidden, resumes on focus.
- `autoRefresh` flag — AUTO/PAUSED toggle, stops/starts 5s interval.
- `chartTimeframes` map — persists selected timeframe per chart, passed to API calls.

---

### `frontend/assets/charts.js`

~230 lines. Chart.js chart factory and management:
- `Charts.create(id, type, config)` — creates chart, stores in internal registry.
- `Charts.updateChart(chart, data)` — updates labels and datasets, calls `chart.update()`.
- `Charts.reThemeAllCharts()` — iterates all registered charts, updates grid/tick/legend colors for dark↔light theme switch.
- Pre-creates all charts on init: index history (line, dual-axis), funding bar, divergence bar, MC distribution bar.
- Theme-aware color helpers: `gridColor()`, `textColor()`.

---

### `frontend/assets/ws.js`

WebSocket client with automatic reconnect:
- Connects to `/ws/live` on init.
- On disconnect: exponential backoff reconnect (1s, 2s, 4s… max 30s). If tab hidden, defers reconnect until tab becomes visible.
- On message: parses JSON, pushes to `App.wsMessageBuffer` for batched flush.
- Updates connection status badge (LIVE/OFFLINE) on connect/disconnect.

---

## Tests (`tests/`)

145 tests across 7 files. Run with `python -m pytest tests/ -q`.

| File | Tests | What it covers |
|------|-------|---------------|
| `test_index_calc.py` | 18 | Tariff index computation, GDELT shock z-score, edge cases |
| `test_shock_calc.py` | 22 | Shock score normalization, empty data, threshold detection |
| `test_divergence_alerts.py` | 20 | Cross-venue spread detection, severity classification, alert generation |
| `test_risk_throttle.py` | 25 | Risk engine guardrails (leverage/margin/daily loss), reducing bypass, cooldown logic |
| `test_paper_trading.py` | 15 | Paper executor open/close/reduce/flip, position tracking, fill events |
| `test_new_features.py` | 18 | Phase 5 features — funding arb, basis engine, stable flow, solana quality, hedge ratio, slippage model, regime replay |
| `test_phase6.py` | 47 | Capital allocator (weights sum to 1, caps/floors, shock/vol sensitivity), vol regime engine (5 regimes, scores, recommendations), backtester (structure, determinism, VaR/CVaR, Sharpe), ML feature store (15 features, finite values, quality), ML inference (heuristic path, no-model path), ML training (insufficient data, mismatched lengths), Redis health fallback, portfolio risk math (`_compute_var_cvar`, `_compute_max_drawdown`, `_compute_sharpe`) |

---

## Event Type Reference

85 event types defined in `backend/core/event_bus.py`. Key groups:

| Group | Types |
|-------|-------|
| Index / Shock | `INDEX_UPDATE`, `SHOCK_SPIKE`, `INDEX_ALERT`, `MACRO_TERMINAL_UPDATE` |
| Market / Prices | `PRICE_UPDATE`, `PRICE_DISLOCATION_ALERT`, `FUNDING_REGIME_FLIP`, `CARRY_UPDATE`, `CARRY_REGIME_FLIP` |
| Divergence | `DIVERGENCE_ALERT`, `DISLOCATION_ALERT` |
| Stablecoins | `STABLE_DEPEG_ALERT`, `STABLE_STRESS_ALERT`, `PEG_BREAK_PROB_UPDATE`, `STABLE_VOLUME_SPIKE`, `STABLE_FUNDING_SPIKE`, `STABLE_FLOW_UPDATE` |
| Prediction | `PREDICTION_UPDATE`, `PREDICTION_CONFIDENCE_LOW` |
| Risk | `RISK_THROTTLE_ON`, `RISK_THROTTLE_OFF`, `RISK_VAR_BREACH` |
| Execution | `ORDER_SENT`, `ORDER_FILLED`, `SWAP_QUOTED`, `SWAP_SENT`, `TRADE_BLOCKED_STALE_DATA`, `TRADE_DEGRADED_DATA`, `EXECUTION_THROTTLE` |
| Agents | `AGENT_SIGNAL`, `AGENT_ACTION_PROPOSED`, `AGENT_BLOCKED` |
| Jupiter / Solana | `JUPITER_QUOTE_STALE`, `JUPITER_SLIPPAGE_SPIKE`, `JUPITER_ROUTE_RISK`, `SOLANA_CONGESTION_WARNING` |
| Portfolio / Strategy | `RULE_ACTION_PROPOSED`, `PORTFOLIO_PROPOSAL`, `ADAPTIVE_WEIGHTS_UPDATE`, `REGIME_ANALOG_MATCH` |
| Microstructure | `MICROSTRUCTURE_SIGNAL`, `LIQUIDITY_THINNING_WARNING` |
| Execution quality | `EXECUTION_METRICS_UPDATE`, `SLIPPAGE_ANOMALY_ALERT` |
| Funding arb / Basis | `FUNDING_ARB_OPPORTUNITY`, `FUNDING_ARB_REGIME_FLIP`, `BASIS_UPDATE`, `BASIS_OPPORTUNITY`, `BASIS_FEASIBILITY_LOW` |
| Hedging | `HEDGE_PROPOSAL`, `HEDGE_REBALANCE_SUGGESTED`, `HEDGE_THROTTLE_RECOMMENDED`, `HEDGE_RATIO_UPDATE` |
| Phase 5 | `SANDBOX_COMPARISON_RUN`, `REPLAY_COMPLETED`, `SLIPPAGE_MODEL_UPDATE`, `SAFE_SIZE_WARNING`, `STABLECOIN_PLAYBOOK_TRIGGERED` |
| Phase 6 | `CAPITAL_ALLOCATION_UPDATE`, `REBALANCE_PREVIEW_CREATED`, `ML_FEATURES_UPDATED`, `ML_MODEL_TRAINED`, `ML_INFERENCE_UPDATE`, `BACKTEST_STARTED`, `BACKTEST_COMPLETED`, `VOL_REGIME_CHANGED`, `PORTFOLIO_RISK_UPDATE`, `REDIS_DEGRADED`, `REDIS_RECOVERED` |
| System | `ERROR`, `STARTUP` |

---

## Redis Key Conventions

All keys use `desk:` prefix with TTLs. State store also supports legacy `index:latest` (both checked).

| Key | TTL | Contents |
|-----|-----|---------|
| `desk:index:latest` / `index:latest` | 300s | Tariff index snapshot |
| `desk:market:latest` | 60s | Multi-venue prices |
| `desk:vol_regime:latest` | 120s | Volatility regime classification |
| `desk:allocation:latest` | 180s | Capital allocation weights |
| `desk:ml:features:latest` | 60s | 15-feature ML vector |
| `desk:ml:prediction:latest` | 60s | Latest inference result |
| `desk:backtest:latest` | 3600s | Last backtest result |
| `desk:portfolio_risk:summary` | 60s | Portfolio risk metrics |
| `desk:risk:throttle` | — | Throttle state (active/reason) |
| `price:pyth:*`, `price:kraken:*`, etc. | 30s | Per-source price ticks |
| `regime:latest` | 300s | Funding/vol regime |
| `predict:latest` | 300s | Macro prediction |
| `funding_arb:latest` | 120s | Funding arb signal |
| `basis:latest` | 120s | Basis spreads |
| `stablecoin:health:latest` | 120s | Stablecoin health |
