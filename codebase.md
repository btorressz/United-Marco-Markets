# Tariff Risk Desk — Codebase Guide

## Root

| File | Purpose |
|------|---------|
| `main.py` | Entry point. Starts Redis, creates the FastAPI app, mounts static files, applies DB migrations, launches the ingest scheduler, and runs Uvicorn on port 5000. |
| `Readme.md` | Project metadata and architecture notes kept in sync as the project evolves. |

---

## Backend (`backend/`)

The backend is a Python/FastAPI application organized into seven packages.

### `backend/config.py`

Centralized configuration loaded from environment variables with safe defaults. Defines execution mode, risk limits, WITS country list, API keys (all optional — fail-open), logging level, and database/Redis URLs.

### `backend/logging_config.py`

Configures structured JSON logging across the entire application.

---

### `backend/api/` — HTTP & WebSocket Routes

Each file is a FastAPI `APIRouter` mounted in `main.py`. Every router is self-contained with its own dependencies. 22 routers total.

| File | Prefix | What it does |
|------|--------|--------------|
| `index_routes.py` | `/api/index` | Tariff Pressure Index latest value, history (with `?window=` support for 1h/4h/1d/7d), components breakdown, alerts, and the Macro Terminal endpoint (tariff series, rolling delta, country weights, correlation heatmap). |
| `markets_routes.py` | `/api/markets` | Multi-venue SOL prices, funding rates, and price integrity check (cross-venue deviation in bps with per-feed timestamps). |
| `divergence_routes.py` | `/api/divergence` | Cross-venue spread analysis and dislocation alerts when venue prices diverge beyond threshold. |
| `stablecoin_routes.py` | `/api/stablecoins` | Stablecoin peg monitoring — latest health, history, stress/depeg analysis, peg-break probability, and alerts. |
| `predict_routes.py` | `/api/predict` | ML-based macro prediction using a sigmoid model over 7 macro features. |
| `montecarlo_routes.py` | `/api/montecarlo` | Monte Carlo VaR/CVaR simulation engine (configurable paths up to 10k, configurable horizon in hours). |
| `yield_routes.py` | `/api/yield` | Carry score calculations — annualized funding yield across venues. |
| `microstructure_routes.py` | `/api/microstructure` | Order book imbalance, basis spread, and bid-ask spread analysis. |
| `agents_routes.py` | `/api/agents` | Runs all registered AI agents (Risk, Macro, Execution, Liquidity, Hyperliquid, Jupiter — 6 active, Hedging agent available backend-only), returns their signals with confidence scores and data timestamps. Also exposes the agent registry. |
| `rules_routes.py` | `/api/rules` | Evaluates the 5-rule strategy engine against current market state. Returns triggered actions. Also exposes `/api/rules/adaptive-weights` for dynamic weight adjustment. |
| `execution_routes.py` | `/api/execution` | Order submission, position listing, and order cancellation. Routes through the ExecutionRouter. |
| `risk_routes.py` | `/api/risk` | Stress test scenarios, risk guardrail status, Monte Carlo risk summary, and `/api/risk/regime-analogs` for regime outcome distribution. |
| `events_routes.py` | `/api/events` | Event timeline — paginated query of all system events from the Postgres event log. |
| `health_routes.py` | `/api/health` | System health check — DB connectivity, Redis status, scheduler state, execution mode. Also exposes `/api/health/feeds` returning per-feed status (Pyth, Kraken, CoinGecko, Hyperliquid, Drift, WITS, GDELT) with last update timestamp, age, and status (ok/warning/error). |
| `ws_routes.py` | `/ws/live` | WebSocket endpoint. Subscribes clients to the Redis pub/sub event stream for real-time updates. |
| `metrics_routes.py` | `/api/metrics` | Execution Quality Index (EQI) — latency p50/p95, slippage stats, anomaly detection per venue. |
| `solana_routes.py` | `/api/solana` | Solana execution quality score (0-100), congestion detection, slippage risk level. |
| `funding_arb_routes.py` | `/api/funding-arb` | HL vs Drift funding rate arbitrage detection — spread, persistence, net carry signal. |
| `basis_routes.py` | `/api/basis` | Perp basis monitor — HL/Drift vs spot annualized basis, net carry, execution feasibility scoring. |
| `stable_flow_routes.py` | `/api/stable-flow` | Stablecoin flow momentum — risk-on/off indicator from stable dominance and peg deviation proxy. |
| `portfolio_routes.py` | `/api/portfolio` | Portfolio construction optimizer — risk_parity, mean_variance, or Kelly proposals with allocation weights and reasoning. |
| `liquidation_routes.py` | `/api/liquidation` | Liquidation heatmap — leverage (1x–10x) vs price drop (5%–50%) grid with probability overlay. |

---

### `backend/core/` — Shared Infrastructure

| File | What it does |
|------|--------------|
| `models.py` | Pydantic models for internal data (PriceTick, FundingTick, DivergenceAlert, etc.). Used for type safety across the system. |
| `schemas.py` | Pydantic response models for API endpoints (IndexLatestResponse, RuleActionResponse, AlertResponse, etc.). |
| `event_bus.py` | Unified event system. Emits 40+ event types to both Redis pub/sub (for WebSocket broadcast) and Postgres (for persistence). All components write to this single bus. Includes Phase 4 types: JUPITER_QUOTE_STALE, JUPITER_SLIPPAGE_SPIKE, plus all Phase 3 types (EXECUTION_METRICS_UPDATE, SLIPPAGE_ANOMALY_ALERT, SOLANA_CONGESTION_WARNING, FUNDING_ARB_OPPORTUNITY, BASIS_UPDATE, STABLE_FLOW_UPDATE, ADAPTIVE_WEIGHTS_UPDATE, PORTFOLIO_PROPOSAL, LIQUIDATION_HEATMAP_UPDATE, etc.). |
| `state_store.py` | Redis-backed snapshot store. Components write latest state (prices, index values, regime) as keyed snapshots with TTLs. Also provides throttle checking for rate-limited alerts. |
| `price_authority.py` | Price cascade logic: Pyth → Kraken → CoinGecko. Returns the best available price with source attribution. |
| `price_validator.py` | Cross-venue price integrity checker. Computes pairwise deviations in bps, flags WARNING when deviation exceeds threshold (default 50bps), emits throttled PRICE_DISLOCATION_ALERT events. |
| `normalization.py` | Normalizes raw data from different venue APIs into consistent internal formats. |
| `timeutils.py` | UTC timestamp helpers and window-string parsing (e.g., "7d" → seconds). |

---

### `backend/compute/` — Pure Computation Modules

Stateless computation functions. No I/O — they take data in and return results. 27 modules total.

| File | What it computes |
|------|-----------------|
| `index_calc.py` | **Tariff Pressure Index** — weighted composite (0–100) combining tariff rates, trade values, and news shock. |
| `shock_calc.py` | **GDELT Shock Score** — z-score of news tone/volume from GDELT data. Detects geopolitical spikes. |
| `divergence.py` | **Cross-venue spread detection** — identifies when the same asset trades at meaningfully different prices across venues. |
| `regime.py` | **Regime classification** — categorizes current funding regime (positive/negative/neutral) and volatility regime (low/normal/high/extreme). |
| `regime_memory.py` | **Regime persistence & outcome library** — stores and replays regime state transitions. Extended with `get_outcome_distribution()` returning avg returns (4h/24h/3d), win rates, and best analog for similar historical regimes. |
| `carry_score.py` | **Annualized carry** — converts periodic funding rates into annualized carry scores for yield comparison. |
| `rules_engine.py` | **5 trading rules** — evaluates configurable rule set: tariff shock hedge, divergence arb, funding flip, vol regime scale, and stable rotation. Returns proposed actions. |
| `risk_engine.py` | **Guardian** — enforces leverage limits, margin usage caps, and daily loss limits. Blocks trades that violate constraints. |
| `stress_tests.py` | **4 scenario stress tests** — simulates tariff escalation, liquidity crisis, stablecoin depeg, and combined shock scenarios against current positions. |
| `stablecoin_health.py` | **Stablecoin peg monitor** — computes depeg magnitude (bps from $1.00), detects stress conditions, and estimates peg-break probability. |
| `macro_predictor.py` | **Sigmoid macro prediction** — 7-feature model predicting macro environment direction (risk-on vs risk-off). |
| `monte_carlo.py` | **Monte Carlo engine** — runs up to 10k simulated price paths to compute VaR and CVaR at configurable confidence levels. |
| `microstructure.py` | **Market microstructure** — order book imbalance, basis between spot and perp, and effective spread analysis. |
| `stable_yield.py` | **Stablecoin yield** — calculates yield/carry opportunities in stablecoin markets. |
| `pnl_attribution.py` | **PnL attribution** — breaks down position-level profit and loss into component factors. |
| `execution_metrics.py` | **Execution Quality Index (EQI)** — tracks order→fill latency, quote→execution delta, expected vs realized slippage. Rolling p50/p95 aggregates per venue (last 100 fills). Detects slippage anomalies via z-score. Returns EQI score (0–100). |
| `solana_liquidity.py` | **Solana liquidity intelligence** — computes execution quality score (0–100), congestion warning (RPC latency + slot delta), and slippage risk level (low/medium/high). Estimates Jupiter route depth and price impact from cached data. |
| `funding_arb.py` | **Funding arb detector** — detects HL vs Drift funding rate divergence. Tracks spread (bps), persistence duration, historical mean. Returns arb signal (long_hl_short_drift / short_hl_long_drift / none) with expected net carry. Rolling history of 100 entries. |
| `basis_engine.py` | **Perp basis engine** — computes HL perp vs Kraken spot, Drift perp vs Pyth oracle, and HL vs Drift perp spread. Returns annualized basis (bps), net carry (basis + funding diff), and execution feasibility score (0–100). Rolling history of 200 entries. |
| `stable_flow.py` | **Stablecoin flow momentum** — computes risk-on/off indicator from stablecoin dominance proxy, peg deviation stress, and volume signals. Returns momentum (-1 to 1), risk_on_off_indicator (risk_on/risk_off/neutral), and explanatory drivers. |
| `adaptive_weights.py` | **Adaptive risk weighting** — dynamically adjusts predictor weights (macro, carry, microstructure, momentum) based on shock score, funding skew, vol regime, and tariff index. Toggled via `ADAPTIVE_WEIGHTS` env var (default on). Default equal weights (25% each), shifted by regime detection. |
| `portfolio_optimizer.py` | **Portfolio construction** — supports risk_parity (default), mean_variance, and scaled Kelly methods. Allocates across hl_perps, drift_perps, spot_jupiter, stablecoins with hard caps (50%/50%/50%/80%) and floors (0%/0%/0%/5%). Returns allocation dict summing to 1.0 with reasoning. Proposals only — never auto-trades. |
| `liquidation_heatmap.py` | **Liquidation heatmap** — computes leverage (1x, 2x, 3x, 5x, 7x, 10x) vs price drop (5%–50%) grid. Each cell = liquidation probability using maintenance margin distance, vol-adjusted probability, and margin usage factor. Monotonicity enforced across both axes. |
| `strategy_sandbox.py` | **Strategy sandbox** — A/B comparison engine for rule configurations. Runs two strategy variants (RulesEngine configs) against the same market state, computes Monte Carlo VaR for each, and returns side-by-side results with triggered actions, rule counts, VaR metrics, and a recommended variant. Stores latest comparison result in memory. |
| `replay_engine.py` | **Replay engine** — deterministic event replay for backtesting. Takes a list of historical market events, replays them through the RulesEngine in sequence, records each step's triggered actions and portfolio state, and produces a summary with total actions, unique rules triggered, final portfolio value, and max drawdown. Stores latest replay result in memory. |
| `slippage_model.py` | **Slippage model** — estimates expected slippage across configurable order size buckets (100–100k USD). Builds slippage curves (bps vs size) from recent fills, computes max safe size for given slippage thresholds (10/25/50 bps), and returns per-venue slippage profiles with curve data, safe sizes, and freshness metadata. |
| `hedge_ratio.py` | **Hedge ratio calculator** — computes rolling correlation, beta, and optimal hedge ratio between asset pairs over a configurable window (default 30 observations, min 5). Returns hedge effectiveness (R²), recommended hedge ratio with confidence level (high/medium/low), and actionable hedge recommendation text. Handles insufficient data gracefully. |
| `stablecoin_playbook.py` | **Stablecoin playbook** — formalized defensive action playbook for depeg scenarios. Evaluates stablecoin health data against tiered thresholds (warn 30bps, alert 50bps, stress >0.5, peg-break probability >0.3) and returns a prioritized list of actions (monitor, reduce_exposure, emergency_exit, diversify, hedge). Each action includes priority (1–5), urgency level (low/medium/high/critical), description, and trigger conditions. |

---

### `backend/agents/` — Heuristic AI Agents

Seven rule-based agents that analyze market state and emit signals with confidence scores (0.70–0.95) and `data_ts_used` timestamps.

| File | Agent | What it monitors |
|------|-------|-----------------|
| `risk_agent.py` | Risk Agent | Liquidation distance warnings, throttle recommendations during high shock + high vol, margin usage alerts. |
| `macro_agent.py` | Macro Agent | Tariff momentum acceleration, GDELT news shock spikes, high tariff regime detection. |
| `execution_agent.py` | Execution Agent | Pre-trade safety checks (spread, liquidity, price integrity), price integrity warnings, high slippage detection. Blocks unsafe trades in live mode. |
| `liquidity_agent.py` | Liquidity Agent | Stablecoin depeg detection, extreme order book imbalance, wide spread / thin liquidity warnings. |
| `hyperliquid_agent.py` | Hyperliquid Agent | HL-specific microstructure signals: orderbook imbalance, spread compression, trade aggression, liquidity thinning. Emits MICROSTRUCTURE_SIGNAL (direction + confidence + reasoning) and LIQUIDITY_THINNING_WARNING events. |
| `jupiter_agent.py` | Jupiter Agent | Jupiter/Solana swap intelligence: quote freshness monitoring, route complexity analysis, price impact estimation, slippage risk assessment, Solana congestion detection. Reuses `solana_liquidity.py` for congestion data. Emits JUPITER_QUOTE_STALE and JUPITER_SLIPPAGE_SPIKE events. |
| `hedging_agent.py` | Hedging Agent | Position-aware hedge recommendations. Analyzes open positions against current regime (vol, shock, funding) and proposes hedge actions (reduce exposure, add hedge, rotate to stables, increase size). Computes hedge urgency score (0–1), suggests hedge ratio based on shock/vol/funding signals, and returns per-position proposals with reasoning. Configurable thresholds for shock, vol, funding, and max hedge ratio. |

---

### `backend/ingest/` — Data Ingestion

All ingest modules are fail-open — if an API is unreachable or a key is missing, the module logs a warning and returns gracefully. Never crashes.

| File | Data Source | Schedule |
|------|------------|----------|
| `scheduler.py` | APScheduler coordinator — registers and runs all 6 ingest jobs on their configured intervals. |
| `wits_ingest.py` | World Bank WITS API — pulls tariff rate data by country/product for the Tariff Pressure Index. |
| `gdelt_ingest.py` | GDELT API — fetches news tone and volume data for the shock score calculation. |
| `kraken_ingest.py` | Kraken REST API — spot prices for SOL, BTC, ETH. Second in the price cascade. |
| `coingecko_ingest.py` | CoinGecko API — fallback spot prices. Third in the price cascade. |
| `pyth_ingest.py` | Pyth Network oracle — on-chain prices. First choice in the price cascade. |
| `drift_ingest.py` | Drift Protocol API — perpetual market data (funding rates, open interest). |
| `hyperliquid_ws.py` | Hyperliquid WebSocket — real-time L2 orderbook and trade data. |

---

### `backend/execution/` — Order Routing

| File | What it does |
|------|--------------|
| `router.py` | Central order router. Checks risk constraints, runs ExecutionAgent pre-trade checks (live mode), enriches all orders with data freshness context (tariff_ts, shock_ts, price_ts, integrity_status), and routes to the appropriate executor. Falls back to paper on live failures. |
| `paper_exec.py` | Paper trading executor. Simulates fills instantly, tracks positions in memory, emits ORDER_SENT and ORDER_FILLED events with full data context. |
| `hyperliquid_exec.py` | Hyperliquid REST executor for live trading. Requires `HYPERLIQUID_API_KEY`. |
| `drift_exec.py` | Drift Protocol executor for live Solana perp trading. Requires `SOLANA_PRIVATE_KEY`. |
| `jupiter_exec.py` | Jupiter aggregator for Solana token swaps. Requires `SOLANA_PRIVATE_KEY`. |
| `solana_tx.py` | Solana transaction construction and signing helper used by Drift and Jupiter executors. |

---

### `backend/data/` — Persistence Layer

| File | What it does |
|------|--------------|
| `db.py` | PostgreSQL connection pool management using psycopg2. Creates and closes the pool on app lifespan. |
| `migrations.sql` | SQL schema — 8 tables: `index_snapshots`, `events`, `market_ticks`, `funding_snapshots`, `positions`, `orders`, `regime_snapshots`, `stablecoin_ticks`. Applied on startup. |

### `backend/data/repositories/` — CRUD Repositories

| File | Table(s) | Operations |
|------|----------|------------|
| `index_repo.py` | `index_snapshots` | Insert snapshots, query latest, query history by time window. |
| `events_repo.py` | `events` | Insert events, query by type/time, paginated listing for the timeline. |
| `market_repo.py` | `market_ticks`, `funding_snapshots` | Insert price ticks, insert funding snapshots, query latest by venue. |
| `positions_repo.py` | `positions`, `orders` | Insert/update positions, insert orders, query open positions. |

---

## Frontend (`frontend/`)

Vanilla HTML/CSS/JS application with Chart.js for charting. No build step, no framework. Light/dark trading desk theme with localStorage persistence.

### `frontend/index.html`

The single-page shell. Contains:
- Header bar with app name, DB/price status indicators, version badge, auto-refresh toggle (pause/resume polling), light/dark theme toggle (SVG sun/moon icons with label), and LIVE WebSocket indicator.
- 8 tab buttons: Index, Markets, Divergence, Stablecoins, Strategy, Execution, Risk, Agents.
- 8 tab content panels (hidden/shown via JS):
  - **Index tab**: Tariff Index / Shock Score / Rate of Change / Last Updated metric cards. Index & Shock History chart with timeframe selector (1h/4h/1d/7d). Macro Prediction panel. Macro Terminal (WITS series, rolling delta, country weights, correlation heatmap). Per-panel freshness badge.
  - **Markets tab**: Multi-venue price table, funding rates, carry scores, microstructure metrics. Solana Execution Quality cards (score, RPC latency, route info). Funding Arbitrage panel (signal, spread, persistence, net carry). Basis Monitor panel (HL-spot, Drift-spot, HL-Drift spread, annualized basis, net carry). Data Feed Status panel (collapsible, showing 7 source statuses). Per-panel freshness badge.
  - **Divergence tab**: Cross-venue spread analysis and dislocation alerts. Per-panel freshness badge.
  - **Stablecoins tab**: Peg monitor table, depeg heatmap, stress/peg-break probability. Stable Flow Momentum panel (momentum value, risk-on/off indicator, drivers).
  - **Strategy tab**: Rule evaluation results (5 rules). Adaptive Risk Weights panel (per-predictor weight bars, adaptive on/off status, adjustments). Portfolio Proposal panel (method, allocation bars with percentages, reasoning).
  - **Execution tab**: Decision Data Status panel (pre-trade data quality warnings — tariff/shock/price freshness, integrity status). Order form, order history, position summary, PnL attribution. Execution Quality Index panel (EQI score, latency p50/p95, avg slippage, fill count, anomalies).
  - **Risk tab**: Stress test scenarios, guardrails. Monte Carlo VaR/CVaR with time unit selector (minutes/hours/days). Regime Replay with outcome distribution (avg 4h/24h returns, win rate, sample count). Liquidation Heatmap (color-coded leverage x drop grid).
  - **Agents tab**: 6 AI agent signals with confidence badges (color-coded percentage), severity/direction badges, expandable reasoning, proposed action display, data timestamps.
- Event timeline bar (always visible at the bottom, color-coded: green=fills, red=errors, yellow=alerts, blue=info, purple=agents).
- Script and stylesheet imports.

### `frontend/assets/styles.css`

Dual-theme trading desk CSS with CSS custom properties:
- **Dark theme (default)**: Dark backgrounds (`#0d1117`, `#161b22`, `#1c2333`), light text (`#e6edf3`), accent colors for green/red/blue/yellow/purple/cyan.
- **Light theme** (`[data-theme="light"]`): Institutional light backgrounds (`#f6f8fa`, `#ffffff`), dark text (`#1f2328`), adjusted accent colors for readability on light backgrounds.
- Theme toggle button styling (SVG icon + text label, monospace font).
- Metric cards with borders and shadows.
- Table styling for market data grids.
- Tab system styling with active/hover states.
- Chart container layouts.
- Responsive event timeline with color-coded event types.
- Status badges (connected/disconnected) and indicator animations (pulse).
- Freshness badges (LIVE/FRESH/STALE/DEGRADED/NO DATA) with color coding.
- Feed status panel styling (collapsible, per-source status rows).
- Timeframe selector buttons (1h/4h/1d/7d).
- Auto-refresh toggle with pulsing green dot.
- Decision data panel styling.
- Agent card styling with confidence badges, expandable sections.
- Liquidation heatmap color scale.
- Scrollbar theming.

### `frontend/assets/app.js`

Main application controller:
- Initializes on DOM load.
- **Theme system**: Reads saved theme from localStorage (default: dark), applies `data-theme` attribute to `<html>`, toggles SVG moon/sun icons and DARK/LIGHT label, triggers Chart.js re-theming. Tracks theme state with a `currentTheme` variable for reliable toggling.
- **Auto-refresh toggle**: Pauses/resumes the 5s polling cycle. Shows "AUTO" with pulsing green dot when active, "PAUSED" when disabled.
- **Timeframe selectors**: 1h/4h/1d/7d buttons on Index chart, passes selected window to history API.
- **Monte Carlo time units**: Minutes/Hours/Days selector next to horizon input, converts to hours before API call, displays human-readable summary.
- Tab switching logic — shows/hides panels, triggers data fetch for the active tab.
- Periodic polling loop (5s interval) that refreshes the active tab's data.
- Each tab refresh function uses `Promise.allSettled` to fetch all data sources in parallel:
  - Index: latest, history, components, health, prediction, macro terminal.
  - Markets: prices, funding, carry, microstructure, integrity, solana quality, funding arb, basis, health/feeds.
  - Divergence: spreads, alerts.
  - Stablecoins: health, alerts, stable flow.
  - Strategy: rules evaluation, adaptive weights, portfolio proposal.
  - Execution: positions, paper trades, EQI, health, integrity.
  - Risk: stress tests, guardrails, monte carlo, regime analogs, liquidation heatmap.
  - Agents: signals, registry.
- **Performance hardening**: `visibilitychange` listener pauses polling when tab is hidden, resumes on focus. WebSocket message buffering (200ms batch interval) prevents rapid DOM thrashing. Tab-aware WS reconnect deferral.
- Calls into `api.js` for data fetching and `ui.js` for rendering.
- Manages the health status indicator and price integrity badge.

### `frontend/assets/api.js`

REST API client. Thin wrapper around `fetch()` with error handling. All endpoints:
- Index: `getIndexLatest()`, `getIndexHistory(window)`, `getIndexComponents()`, `getMacroTerminal()`
- Markets: `getMarketLatest()`, `getFunding()`, `getIntegrity()`, `getCarry()`, `getMicrostructure()`
- Stablecoins: `getStablecoinHealth()`, `getStablecoinAlerts()`
- Strategy: `getRulesEvaluation()`, `getRulesStatus()`
- Execution: `getPositions()`, `getPaperTrades()`, `postOrder()`
- Risk: `getRiskStatus()`, `getGuardrails()`, `postStressTest()`, `postMonteCarlo()`
- Agents: `getAgentSignals()`, `getAgentRegistry()`
- Prediction: `getPrediction()`
- Events: `getEvents()`
- Health: `getHealth()`, `getFeedStatus()`
- Phase 3: `getEQI()`, `getSolanaQuality()`, `getSolanaCongestion()`, `getFundingArb()`, `getBasisLatest()`, `getBasisFeasibility()`, `getStableFlow()`, `getAdaptiveWeights()`, `getPortfolioProposal()`, `getLiquidationHeatmap()`, `getRegimeAnalogs()`

### `frontend/assets/ui.js`

UI rendering functions — one per tab/section:
- `renderIndexTab()` — Tariff index, shock score, rate of change metric cards + macro prediction panel + freshness badge.
- `renderMacroTerminal()` — WITS tariff series, rolling delta, country weights, correlation heatmap with empty-state fallbacks.
- `renderMarketsTab()` — Multi-venue price table, funding rates, carry scores, microstructure metrics, price integrity badge. Solana quality cards (score with color coding, RPC latency, congestion status, route info). Funding arb metric row (signal, spread bps, persistence, net carry). Basis monitor metric row (HL-spot, Drift-spot, HL-Drift spread, annualized basis, net carry). Freshness badge.
- `renderFeedStatus()` — Collapsible data feed status panel showing all 7 sources (Pyth, Kraken, CoinGecko, Hyperliquid, Drift, WITS, GDELT) with status badges (ok/warning/error) and last update age.
- `renderDivergenceTab()` — Spread analysis table with alert highlighting + freshness badge.
- `renderStablecoinsTab()` — Peg monitor table, depeg heatmap, stress indicators, peg-break probability bars. Stable flow momentum panel with risk-on/off indicator and driver list.
- `renderStrategyTab()` — Rule evaluation results with action type badges. Adaptive weights metric row with per-predictor percentages and adjustment notes. Portfolio proposal with allocation bars and reasoning.
- `renderExecutionTab()` — Order history table, position summary, PnL display. Decision Data Status panel showing pre-trade data quality (system health, price integrity, tariff index freshness) with warnings for degraded data. EQI panel with score (color-coded), latency p50/p95, avg slippage, fill count, anomaly list.
- `renderRiskTab()` — Stress test scenario cards, guardrail status, Monte Carlo VaR/CVaR results. Liquidation heatmap as color-coded HTML table (green→yellow→red by probability). Regime analog outcome distribution (avg returns, win rate, sample count).
- `renderAgentsTab()` — Agent signal cards with confidence badges (color-coded percentage), severity/direction badges, expandable reasoning sections, proposed action display, data timestamps.
- `renderFreshnessBadge()` — Reusable freshness indicator showing LIVE (green, <10s), FRESH (blue, <60s), STALE (yellow, <300s), DEGRADED (red, >300s), or NO DATA states with data age.
- `renderTimeline()` / `addEventToTimeline()` — Color-coded event timeline (green=fills, red=errors, yellow=alerts, blue=info, purple=agents).

### `frontend/assets/charts.js`

Chart.js chart management:
- `createIndexChart()` — Dual-axis line chart for Tariff Index and Shock Score history.
- `createFundingChart()` — Bar chart for funding rates across venues.
- `createDivergenceChart()` — Chart for cross-venue spreads.
- `createMCChart()` — Histogram/distribution chart for Monte Carlo simulation results.
- `updateChart()` — Efficient chart data updates without full re-creation.
- `getThemeColors()` — Reads CSS custom properties at runtime to get current theme colors for chart elements.
- `reThemeAllCharts()` — Updates all chart instances (grid, tick, tooltip, legend colors) from current CSS variables when theme changes. Called after theme toggle with a 50ms delay to allow CSS to cascade.
- Chart theme configuration adapts to both dark and light themes via CSS variable-driven colors.

### `frontend/assets/ws.js`

WebSocket client:
- Connects to `/ws/live` with automatic reconnection (exponential backoff, max 30s).
- Parses incoming event messages and dispatches to UI update handlers.
- Updates the LIVE indicator in the header.
- Connection state management (connected/disconnected/reconnecting).
- Tab-aware reconnect: defers reconnection attempts when browser tab is hidden.
- Message buffering: batches rapid WS messages at 200ms intervals to prevent DOM thrashing.

---

## Tests (`tests/`)

77 tests across 5 test files:

| File | What it tests |
|------|---------------|
| `test_index_calc.py` | Tariff Pressure Index calculation — weighted composition, edge cases, boundary values. |
| `test_shock_calc.py` | GDELT shock score — z-score computation, spike detection thresholds, empty data handling. |
| `test_divergence_alerts.py` | Cross-venue divergence — spread calculation, alert triggering, multi-venue scenarios. |
| `test_risk_throttle.py` | Risk engine constraints — leverage limits, margin caps, daily loss limits, blocking behavior. |
| `test_new_features.py` | Phase 3 features — basis engine calculations, funding arb detection (no signal, long HL, short HL), stable flow momentum (healthy/stress/empty), adaptive weights (default/high shock/high vol), portfolio optimizer (risk parity/mean variance/kelly, cap enforcement), liquidation heatmap (shape, monotonicity across leverage and drop axes, probability bounds), execution metrics (EQI score, slippage anomaly detection), Solana liquidity (quality score, congestion detection). |

---

## Phase 4 Features Summary

Phase 4 added 12 UX/frontend improvements on top of the Phase 3 backend:

1. **Light/Dark Theme Toggle** — SVG moon/sun icons with DARK/LIGHT label in header. Persists in localStorage. Sets `[data-theme="light"]` on `<html>` to override CSS custom properties. Re-themes all Chart.js charts via `reThemeAllCharts()`.
2. **Chart Timeframe Selectors** — 1h/4h/1d/7d buttons on Index chart. Passes selected window parameter to history API.
3. **Auto-Refresh Toggle** — Header button to pause/resume the 5s polling cycle. Shows "AUTO" (pulsing green dot) when active, "PAUSED" when disabled.
4. **Monte Carlo Time Units** — Minutes/Hours/Days dropdown next to horizon input. Converts to hours for backend. Displays human-readable summary.
5. **Per-Panel Freshness Badges** — Reusable LIVE/FRESH/STALE/DEGRADED/NO DATA indicators on Index, Markets, Divergence panels with color coding and data age.
6. **Data Feed Status Panel** — Collapsible panel in Markets tab showing all 7 data sources with status badges. Backed by `/api/health/feeds` endpoint.
7. **JupiterAgent** — 6th AI agent monitoring quote freshness, route complexity, price impact, slippage risk, and Solana congestion.
8. **Improved Agent UI** — Confidence badges (colored percentage), expandable reasoning sections, proposed action display, severity/direction badges, data timestamps.
9. **Decision Data Status** — Pre-trade panel in Execution tab showing data quality warnings (system health, price integrity, tariff index freshness).
10. **Macro Terminal Completeness** — All 4 sections (WITS series, rolling delta, country weights, correlation heatmap) render with empty-state fallbacks.
11. **Performance Hardening** — `visibilitychange` pauses polling when tab hidden. WS messages batched at 200ms. Tab-aware reconnect deferral.
12. **Event Bus Updates** — Added JUPITER_QUOTE_STALE and JUPITER_SLIPPAGE_SPIKE event types.

---

## Phase 5 Backend Modules Summary

Phase 5 added 6 new backend modules expanding the compute and agent layers. These are backend-only (no API routes or frontend integration yet):

1. **Hedging Agent** (`backend/agents/hedging_agent.py`) — 7th AI agent providing position-aware hedge recommendations. Evaluates open positions against current shock, vol, and funding regime to produce per-position hedge proposals with urgency scores and suggested actions (reduce, hedge, rotate, increase).
2. **Strategy Sandbox** (`backend/compute/strategy_sandbox.py`) — A/B strategy comparison engine. Runs two RulesEngine configurations side-by-side against the same market state, evaluates Monte Carlo VaR for each variant, and recommends the better-performing strategy.
3. **Replay Engine** (`backend/compute/replay_engine.py`) — Deterministic event replay for backtesting. Replays sequences of historical market events through the RulesEngine, recording triggered actions and portfolio state at each step to produce backtesting summaries.
4. **Slippage Model** (`backend/compute/slippage_model.py`) — Slippage curve estimator. Builds bps-vs-size curves from recent fills across venues, computes max safe order sizes for given slippage thresholds, and provides per-venue slippage profiles.
5. **Hedge Ratio Calculator** (`backend/compute/hedge_ratio.py`) — Rolling correlation and beta calculator for asset pairs. Computes optimal hedge ratio, hedge effectiveness (R²), and confidence level over configurable observation windows.
6. **Stablecoin Playbook** (`backend/compute/stablecoin_playbook.py`) — Formalized defensive action playbook for stablecoin depeg scenarios. Evaluates health data against tiered thresholds and returns prioritized actions (monitor → reduce → exit → diversify → hedge) with urgency levels.

---

## Data Flow Summary

```
External APIs (WITS, GDELT, Kraken, CoinGecko, Pyth, Drift, Hyperliquid)
        │
        ▼
   ingest/ (scheduled jobs, fail-open)
        │
        ▼
   core/state_store (Redis snapshots)  ──►  core/event_bus (Redis pub/sub + Postgres)
        │                                          │
        ▼                                          ▼
   compute/ (pure calculations)              ws_routes.py (WebSocket broadcast)
        │                                          │
        ▼                                          ▼
   api/ (REST endpoints)                    Frontend (real-time updates)
        │                                          │
        ▼                                          ▼
   agents/ (7 heuristic AI agents)         Theme/Freshness/Feed UI
        │
        ▼
   execution/router (risk check → agent check → paper/live fill)
        │
        ▼
   data/repositories (Postgres persistence)
```
