# United-Marco-Markets (Tariff Risk Desk)

**NOTE** : This project is for research and development purposes ONLY at the moment. 



## Overview
This project is a unified macro-to-markets risk management desk that transforms trade policy and geopolitical signals into actionable market intelligence. It monitors global tariff data and news sentiment to create a Tariff Pressure Index, integrates with live crypto market data from multiple sources, employs heuristic AI agents for risk analysis, and provides execution capabilities across various platforms. The system prioritizes safety with a default paper mode and a fail-open design, all presented through a dark/light theme trading desk dashboard.

## User Preferences
- Dark theme trading desk aesthetic (default, with light mode option)
- No React — vanilla JS + Chart.js only
- Structured logging (JSON format)
- Fail-open, never crash
- Paper mode by default

## System Architecture

### Core Design Principles
The system is built on a fail-open philosophy, where missing API keys or unavailable data sources disable features without crashing the system. It defaults to paper mode for execution, ensuring no real money is at risk unless explicitly configured. A unified event bus, utilizing Redis pub/sub and PostgreSQL persistence, centralizes all system events (104 total event types). Price data integrity is maintained through a cascading authority model (Pyth → Kraken → CoinGecko) with cross-venue validation. The frontend is WebSocket-first for live updates, complemented by 5-second REST polling. Heuristic, rule-based AI agents provide deterministic and explainable insights, with portfolio optimizers offering proposals rather than autonomous trading. Performance is optimized through mechanisms like pausing polling on hidden tabs and batching WebSocket messages.

### Backend (Python/FastAPI)
The backend is a FastAPI application with 33 registered API routers covering:
- **Core data**: Tariff index, market prices, divergence, stablecoins, prediction, events
- **Risk & execution**: Risk engine (VaR/CVaR), Monte Carlo simulation, execution routing, guardrails
- **Market data**: Microstructure, carry scores, funding arbitrage, basis monitor, stable flow
- **Advanced**: Liquidation heatmap, regime replay, Solana execution quality, hedging
- **Phase 6 additions**: Capital allocation, ML feature store + inference, historical backtesting, volatility regime, portfolio risk dashboard

**Compute modules** (`backend/compute/`):
- `tariff_index.py`, `shock_score.py` — Tariff Pressure Index + shock detection
- `divergence.py`, `regime.py`, `carry_score.py`, `risk_engine.py` — Market analysis
- `capital_allocator.py` — Risk-weighted capital allocation across 5 venues (Hyperliquid, Drift, Jupiter, Stablecoins, Cash)
- `vol_regime_engine.py` — Volatility regime classifier (5 regimes: low/normal/high/shock/liquidity_crunch)
- `backtester.py` — Deterministic historical backtest with equity curve, Sharpe, max drawdown, VaR/CVaR, per-strategy P&L
- `solana_liquidity.py` — Solana execution quality scoring
- `strategy_performance.py` — Per-strategy PnL, Sharpe, max drawdown, win rate from trade history (Phase 7)
- `smart_execution.py` — In-memory TWAP/VWAP slice tracking with slippage estimation (Phase 7)

**ML Package** (`backend/ml/`):
- `feature_store.py` — Builds 15-feature vector from live state (tariff index, shock, vol, sentiment, carry, stablecoin health, etc.)
- `training.py` — Offline-only training scaffold (logistic regression / LightGBM optional); heuristic fallback always active
- `inference.py` — Prediction endpoint; returns probability, confidence, model_type, top drivers
- `explainability.py` — Feature importance / SHAP (fail-open if SHAP unavailable)

**Agents** (`backend/agents/`): risk, macro, execution, liquidity, hyperliquid, hedging, **jupiter** agents (7 total) — all proposal-only, deterministic, emit structured signals with confidence/reasoning/data timestamps.

- **JupiterAgent**: Monitors quote freshness, route complexity, price impact, slippage risk, Solana congestion. Emits JUPITER_QUOTE_STALE, JUPITER_ROUTE_COMPLEX, JUPITER_PRICE_IMPACT_HIGH, JUPITER_SLIPPAGE_SPIKE signals with confidence 0.70–0.95.

**Infrastructure** (`backend/core/`): event_bus (104 event types), state_store (Redis with in-memory fallback), price_validator, normalizer, schemas

**Data ingestion** (`backend/ingest/`): APScheduler jobs — World Bank WITS, GDELT, Kraken, CoinGecko, Pyth, Drift, Hyperliquid, Solana

### Frontend (Vanilla HTML/CSS/JS + Chart.js)
Single-page application with 8-tab dashboard. Dark/light theme, no React, Chart.js only.

**Dashboard Tabs:**
- **Index**: Tariff Pressure Index, Shock Score, Rate of Change, Index+Shock history chart (1h/4h/1d/7d timeframes), Components table, 4h Prediction panel, Macro Terminal (WITS series, Rolling delta, Country weights, Correlation heatmap)
- **Markets**: Multi-venue prices with freshness badges, Funding rates chart, Carry scores, Microstructure (OB imbalance, basis), Solana execution quality, Funding arb monitor, Basis monitor, Price integrity, Feed status panel (collapsible)
- **Divergence**: Cross-venue spread analysis, spread bar chart, dislocation alerts
- **Stablecoins**: Peg monitor, depeg heatmap, stress/peg-break probability, stable flow momentum, risk on/off indicator
- **Strategy**: Active rule signals, Registered rules, Adaptive risk weights, Portfolio proposal (risk_parity), **Capital Allocation** (weighted bars by venue, RAR, confidence), **ML Signal Layer** (BTC up probability, confidence, top feature drivers), **Historical Backtest** (form: strategy/window/capital/venue/fees → Sharpe, return, drawdown, equity curve SVG)
- **Execution**: Decision data status, paper/live trades, positions, P&L attribution, Execution Quality Index
- **Risk**: Throttle banner, **Portfolio Risk Dashboard** (exposure breakdown, VaR/CVaR, concentration risk), **Volatility Regime** (5-regime classifier + recommendations), Leverage/margin/PnL metrics, Guardrails, Stress test, Monte Carlo VaR/CVaR (with minutes/hours/days time unit), Regime replay (analogs), Liquidation heatmap
- **Agents**: Agent status (7 agents), AI agent signals with confidence badges, expandable reasoning, proposed action status, data timestamps; Agent registry

**UX Features:**
- Light/dark theme toggle (localStorage persistent, re-themes Chart.js) — `[data-theme="light"]` CSS variables + toggle button
- Chart timeframe selectors (1h/4h/1d/7d on Index chart) — `.timeframe-selector` with `.tf-btn` pattern
- Auto-refresh toggle (pauses 5s polling) — `#auto-refresh-toggle` in header
- Tab visibility listener (pauses polling when browser tab hidden) — `document.visibilitychange` event
- Per-panel freshness badges (LIVE/FRESH/STALE/DEGRADED/NO DATA) — `renderFreshnessBadge(id, ts, thresholds)`
- Collapsible feed status panel in Markets tab — toggle button + `display:none/block`
- Monte Carlo time unit selector (minutes/hours/days) — converts to hours before API call
- WebSocket message batching (200ms flush buffer) — `wsMessageBuffer` + `wsFlushTimer`
- Backtest form with live results + equity curve SVG — `#backtest-form` → `renderBacktestPanel()`
- Pre-trade decision data status panel (integrity/staleness warnings) — `renderDecisionDataPanel()`

**CSS Variables:**
- Dark theme (`:root`): `--bg-primary`, `--bg-secondary`, `--bg-card`, `--bg-tertiary`, `--bg-input`, `--border-color`, `--border-highlight`, `--text-primary`, `--text-secondary`, `--text-muted`, accent colors
- Light theme (`[data-theme="light"]`): All variables overridden for institutional light look

**Key files:**
- `frontend/index.html` — Single HTML file, 8 tabs, all panel containers
- `frontend/assets/styles.css` — CSS variables (dark/light incl. `--bg-tertiary`), all component styles
- `frontend/assets/api.js` — All REST API methods (~50 endpoints)
- `frontend/assets/ui.js` — All render functions (~1,300 lines)
- `frontend/assets/app.js` — Tab orchestration, form handlers, WS, polling
- `frontend/assets/charts.js` — Chart.js chart creation and re-theming
- `frontend/assets/ws.js` — WebSocket client with reconnect + tab-hidden deferral

## Paper Trading Behavior
- **SELL behavior**: Opens short (no position), reduces/closes long (existing position), or flips long→short (oversized sell)
- **BUY behavior**: Opens long (no position), reduces/closes short (existing position), or flips short→long (oversized buy)
- **Risk bypass for reduces**: Selling to reduce/close a long (or buying to close a short) bypasses cooldown, throttle, leverage, margin, and daily loss checks — you can always exit
- **Cooldown**: 300s cooldown only enforced in live mode; paper mode has no cooldown between trades
- **Live price injection**: Orders without explicit price auto-fill from the Pyth→Kraken→CoinGecko cascade
- **Freshness threshold**: `PRICE_FRESHNESS_THRESHOLD_S` (default 30s) — stale data blocks live trades, tags paper trades as DEGRADED
- **Integrity enforcement**: Price integrity WARNING blocks live trades (configurable via `PRICE_INTEGRITY_BLOCK_LIVE`), tags paper trades as DEGRADED
- **Event types**: `TRADE_BLOCKED_STALE_DATA` (blocked), `TRADE_DEGRADED_DATA` (allowed with tag)

## Logging Configuration
- Structured JSON logging via `backend/logging_config.py`
- APScheduler loggers set to WARNING (no "Running job..." noise during trades)
- urllib3, httpx, redis loggers set to WARNING
- Application trade logs (ORDER_SENT, ORDER_FILLED) remain at INFO

## Redis Key Conventions
All keys use `desk:` prefix with TTLs. Key snapshots:
- `desk:index:latest` / `index:latest` — Tariff index (both supported)
- `desk:vol_regime:latest` — Volatility regime classification
- `desk:allocation:latest` — Capital allocation weights
- `desk:ml:features:latest` — Feature vector for ML
- `desk:ml:prediction:latest` — Latest ML inference result
- `desk:backtest:latest` — Last backtest result
- `desk:portfolio_risk:summary` — Portfolio risk metrics
- `desk:risk:throttle` — Throttle state
- `desk:market:latest` — Latest multi-venue prices

## Phase 6 API Endpoints (additions)
- `GET /api/allocation/latest` — Capital allocation proposal
- `POST /api/allocation/rebalance-preview` — Rebalance preview with target weights
- `GET /api/ml/features/latest` — Latest feature vector
- `GET /api/ml/prediction/latest` — Latest ML/heuristic prediction
- `POST /api/ml/train/offline` — Offline model training (samples + labels)
- `GET /api/ml/training/history` — Training run history
- `POST /api/backtest/run` — Run historical backtest (strategy, window_days, capital, venue, fees)
- `GET /api/backtest/latest` — Latest backtest result from Redis
- `GET /api/backtest/history` — Backtest run history
- `GET /api/volatility/regime` — Current volatility regime + scores
- `GET /api/volatility/recommendations` — Regime-specific trading recommendations
- `GET /api/portfolio-risk/summary` — Portfolio risk metrics (VaR, CVaR, exposure, concentration)
- `GET /api/portfolio-risk/contributions` — Per-position risk contributions
- `GET /api/portfolio-risk/exposures` — Long/short/net exposure breakdown
- `GET /api/health/redis` — Redis health (ping, memory, key count, fallback mode)
- `GET /api/health/feeds` — Per-feed status (Pyth, Kraken, CoinGecko, HL, Drift, WITS, GDELT) with age, status, authority flag

## Database Schema
Tables: `events`, `index_history`, `market_ticks`, `funding_ticks`, `positions`, `paper_trades` (+ `strategy_id`, `slippage_bps` columns), `regime_snapshots`, `stablecoin_ticks`, `conditional_orders`

## Test Suite
145 tests across 7 files:
- `tests/test_tariff_index.py` — Tariff index computation
- `tests/test_agents.py` — Agent signal generation (includes JupiterAgent)
- `tests/test_execution.py` — Paper execution engine
- `tests/test_risk_engine.py` — Risk guardrails and throttle
- `tests/test_event_bus.py` — Event bus and state store
- `tests/test_phase5b.py` — Solana quality, funding arb, basis, stable flow, hedging, regime replay
- `tests/test_phase6.py` — Capital allocator, vol regime, backtester, ML feature store, ML inference, ML training, Redis health fallback, portfolio risk calculations

## External Dependencies
- **PostgreSQL**: Replit-managed database for persistent storage of market data, events, and positions.
- **Redis**: Used for caching, real-time state management, and the event bus (pub/sub).
- **Pyth Network**: Primary oracle for price data.
- **Kraken**: Cryptocurrency exchange for spot prices and a fallback price source.
- **CoinGecko**: Cryptocurrency data aggregator, serving as a secondary fallback price source.
- **World Bank WITS**: Source for global tariff data.
- **GDELT Project**: Source for news and sentiment data.
- **Hyperliquid**: Cryptocurrency exchange for market data and execution.
- **Drift Protocol**: Decentralized exchange for perpetuals market data and execution.
- **Jupiter Aggregator**: Solana-based swap aggregator for execution.
- **Chart.js**: JavaScript charting library for frontend data visualization.
- **FastAPI**: Python web framework for building the backend API.
- **Uvicorn**: ASGI server for running the FastAPI application.
- **APScheduler**: Python library for scheduling periodic tasks for data ingestion.
- **psycopg2**: PostgreSQL adapter for Python.
- **pytest**: Python testing framework.
- **LightGBM** (optional): ML training backend; heuristic fallback if unavailable.
- **SHAP** (optional): ML explainability; skipped gracefully if unavailable.


## 2026 Equity + Execution Safety Expansion

This phase adds a proposal-only equities layer and strengthens paper-mode trading-desk controls without changing the core architecture. The backend remains FastAPI, the frontend remains vanilla HTML/CSS/JS with Chart.js, and paper mode remains the default.

### Equity market features
- New `/api/equities/*` router for overview, quotes, historical OHLCV, watchlists, risk signals, tariff exposure, sector rotation, and cross-asset risk.
- yfinance is the primary MVP research-grade source, Stooq is an EOD fallback, and deterministic mock/demo equity data is always available when providers fail or dependencies are missing.
- Equity analytics include daily/5D/1M return, realized volatility, max drawdown, moving averages, RSI, beta proxy, relative strength vs SPY, volume vs average volume, sector labels, provider status, and data timestamps.
- The universe includes SPY, QQQ, DIA, IWM, major sector ETFs, semiconductor/defense/retail/China/EM ETFs, and tariff-sensitive single names across tech, retail, autos, machinery, aerospace, energy, copper, and steel.
- New heuristic proposal-only agents cover equity risk, tariff exposure, and sector rotation with structured explainable signals.

### Execution, allocation, replay, data quality, and memory upgrades
- Allocation recommendations now feed a proposal-only pre-trade sizing preview at `POST /api/allocation/execution-preview`.
- Paper-mode conditional order endpoints support stop loss, take profit, trailing stop, and bracket order records, with fail-open evaluation and no autonomous live trading.
- Smart execution endpoints support TWAP/VWAP schedule generation, slice plans, estimated slippage, and status tracking in paper/proposal mode.
- Strategy performance is exposed at `GET /api/strategy/performance` with PnL, Sharpe, drawdown, win rate, slippage, trade count, exposure placeholders, and allocator feedback.
- Data quality is exposed at `GET /api/health/data-quality` across crypto, macro, and equity providers with freshness, fallback, degraded mode, confidence, and source-priority fields.
- Replay trade simulation at `POST /api/replay/trade-simulation` produces simulated signals, allocation changes, paper trade decisions, final portfolio value, drawdown, and per-strategy PnL without executing trades.
- Agent memory endpoints `GET /api/agents/performance` and `GET /api/agents/history` summarize deterministic signal history and outcome placeholders.

### Frontend additions
- A new **Equities** tab adds market overview cards, sector ETF table, tariff-sensitive watchlist, selected ticker Chart.js chart, tariff exposure panel, equity agent signals, cross-asset risk panel, and provider freshness badges.
- Existing Strategy, Execution, Risk, and Agents tabs receive additive panels for strategy performance, allocation preview, advanced paper orders, replay simulation, data quality, and agent memory.

## 2026 Institutional Intelligence Layer

This phase adds an institutional-style macro intelligence layer on top of the equity/execution expansion while preserving the existing FastAPI + vanilla JS architecture and paper-mode defaults.

### New institutional intelligence features
- **Macro event calendar and impact tracker** via `/api/macro/events`, `/api/macro/events/impact`, and `/api/macro/events/{id}/reaction`, using WITS/GDELT snapshots when present and deterministic demo events when unavailable.
- **Tariff beta and macro sensitivity** via `/api/macro-sensitivity/assets` and `/api/macro-sensitivity/{ticker}`, with transparent component scoring and degraded flags.
- **Cross-asset correlation and contagion** via `/api/cross-asset/correlations` and `/api/cross-asset/contagion`, covering tariff shock, equity weakness, crypto risk-off, stablecoin stress, and semiconductor-to-QQQ pressure.
- **Scenario builder** via `/api/scenario/templates` and `/api/scenario/run`, producing proposal-only PnL impact, agent signals, allocation changes, hedge recommendations, triggered conditional-order names, and execution warnings.
- **Cross-asset hedging** via `/api/hedge/cross-asset` and `/api/hedge/preview`, extending hedge recommendations across equities, ETFs, crypto, stables, and cash.
- **Portfolio explainability** via `/api/explain/portfolio` and `/api/explain/recommendation/{id}` with drivers, agent agreement, data freshness, confidence, invalidation conditions, and expected upside/downside.
- **Agent consensus and signal attribution** via `/api/agents/consensus`, `/api/signals/outcomes`, and `/api/signals/attribution`.
- **Watchlists and reports** via `/api/watchlists` and `/api/reports/*`, using in-memory fallback and JSON/copy-friendly report structures.

### Safety notes
All new outputs are deterministic, heuristic, explainable, and proposal-only. Missing WITS, GDELT, yfinance, Stooq, Redis, Postgres, or market data returns degraded but valid JSON. No React was added, paper mode remains the default, and live trading behavior is unchanged.
