# United-Marco-Markets (Tariff Risk Desk)

## Overview
A unified macro-to-markets risk desk that turns trade policy and geopolitical signals into actionable market intelligence. Features a live Tariff Pressure Index, market divergence detection, rule-based portfolio actions, stress tests, ML prediction, Monte Carlo risk, stablecoin monitoring, 6 AI agents, execution quality tracking, funding arb detection, basis engine, portfolio optimization, liquidation heatmap, light/dark theme, freshness indicators, feed status monitoring, and optional execution via Hyperliquid, Drift, and Jupiter.

## Current State
- **Status**: Phase 4 complete, paper mode active
- **Backend**: FastAPI on port 5000
- **Frontend**: Vanilla HTML/CSS/JS + Chart.js (light/dark trading desk theme, 8 tabs)
- **Database**: PostgreSQL (Replit managed, 8 tables)
- **Cache/PubSub**: Redis (local, started by main.py)
- **Execution Mode**: Paper (default, safe)

## Architecture

### Backend (Python/FastAPI)
```
backend/
  main.py          - App factory with lifespan (DB init + scheduler)
  config.py        - Env-based configuration, fail-open defaults
  logging_config.py - Structured JSON logging

  api/              - FastAPI routers (22 routers)
    index_routes.py       - /api/index/* (tariff index data, macro-terminal)
    markets_routes.py     - /api/markets/* (venue prices/funding/integrity)
    divergence_routes.py  - /api/divergence/* (spread alerts)
    stablecoin_routes.py  - /api/stablecoins/* (peg monitor, stress, alerts)
    predict_routes.py     - /api/predict/* (ML macro prediction)
    montecarlo_routes.py  - /api/montecarlo/* (VaR/CVaR, float horizon)
    yield_routes.py       - /api/yield/* (carry scores)
    microstructure_routes.py - /api/microstructure/* (OB imbalance, basis)
    agents_routes.py      - /api/agents/* (6 AI agent signals + registry)
    rules_routes.py       - /api/rules/* (strategy eval, 5 rules, adaptive weights)
    execution_routes.py   - /api/execution/* (orders, positions)
    risk_routes.py        - /api/risk/* (stress tests, guardrails, regime analogs)
    events_routes.py      - /api/events/* (event timeline)
    health_routes.py      - /api/health/ (system status + /feeds endpoint)
    ws_routes.py          - /ws/live (WebSocket live feed)
    metrics_routes.py     - /api/metrics/* (EQI, latency stats)
    solana_routes.py      - /api/solana/* (execution quality, congestion)
    funding_arb_routes.py - /api/funding-arb/* (arb signals)
    basis_routes.py       - /api/basis/* (basis monitor, feasibility)
    stable_flow_routes.py - /api/stable-flow/* (flow momentum)
    portfolio_routes.py   - /api/portfolio/* (optimizer proposals)
    liquidation_routes.py - /api/liquidation/* (heatmap)

  core/             - Shared models, bus, store
    models.py         - Pydantic models (PriceTick, FundingTick, etc.)
    schemas.py        - API response schemas
    event_bus.py      - Redis pubsub + Postgres event log (40+ event types)
    state_store.py    - Redis snapshot/throttle store
    price_authority.py - Pyth > Kraken > CoinGecko price cascade
    price_validator.py - Cross-venue price integrity checker
    normalization.py  - Venue data normalizers
    timeutils.py      - UTC timestamp helpers

  compute/          - Pure computation modules (22 modules)
    index_calc.py     - Tariff Pressure Index (weighted, 0-100)
    shock_calc.py     - GDELT news shock z-score
    divergence.py     - Cross-venue spread detection
    regime.py         - Funding/vol regime classification
    carry_score.py    - Annualized carry computation
    rules_engine.py   - 5 configurable trading rules (incl. stable rotation)
    risk_engine.py    - Guardian (leverage/margin/loss limits)
    stress_tests.py   - 4 scenario stress tests
    stablecoin_health.py - Stablecoin peg/depeg/stress monitoring
    macro_predictor.py - Sigmoid-based macro prediction (7 features)
    monte_carlo.py    - Monte Carlo VaR/CVaR engine (max 10k paths, float hours)
    microstructure.py - OB imbalance, basis, spread analysis
    stable_yield.py   - Stablecoin yield/carry calculations
    pnl_attribution.py - Position-level PnL attribution
    regime_memory.py  - Regime state persistence, replay, outcome distribution
    execution_metrics.py - Execution Quality Index (EQI), latency p50/p95, slippage
    solana_liquidity.py  - Solana execution quality score, congestion detection
    funding_arb.py    - HL vs Drift funding rate arb detection
    basis_engine.py   - Perp basis engine (annualized basis, net carry, feasibility)
    stable_flow.py    - Stablecoin flow momentum, risk-on/off indicator
    adaptive_weights.py - Dynamic predictor weight adjustment by regime
    portfolio_optimizer.py - Portfolio construction (risk_parity, mean_variance, kelly)
    liquidation_heatmap.py - Leverage vs price drop liquidation probability grid

  agents/           - Heuristic AI agents (6 agents)
    risk_agent.py     - Risk monitoring and position sizing
    macro_agent.py    - Macro environment analysis
    execution_agent.py - Order timing and venue selection
    liquidity_agent.py - Liquidity and spread monitoring
    hyperliquid_agent.py - Hyperliquid microstructure signals
    jupiter_agent.py  - Jupiter/Solana swap intelligence (quote freshness, route complexity, price impact)

  ingest/           - Data ingestion (all fail-open)
    scheduler.py      - APScheduler with 6 periodic jobs
    wits_ingest.py    - World Bank WITS tariff data
    gdelt_ingest.py   - GDELT news/tone data
    kraken_ingest.py  - Kraken spot prices
    coingecko_ingest.py - CoinGecko fallback prices
    pyth_ingest.py    - Pyth oracle prices
    drift_ingest.py   - Drift perp market data
    hyperliquid_ws.py - Hyperliquid WebSocket client

  execution/        - Order routing (paper + live)
    router.py         - Routes orders based on EXECUTION_MODE
    paper_exec.py     - Paper trading with position tracking
    hyperliquid_exec.py - Hyperliquid REST execution
    drift_exec.py     - Drift REST execution
    jupiter_exec.py   - Jupiter swap routing
    solana_tx.py      - Solana transaction helper

  data/             - Persistence layer
    db.py             - Postgres connection pool
    migrations.sql    - Schema (8 tables incl. regime_snapshots, stablecoin_ticks)
    repositories/     - CRUD for each entity
```

### Frontend
```
frontend/
  index.html        - 8-tab dashboard with Phase 4 UX improvements
  assets/
    styles.css      - Light/dark trading desk theme + freshness/feed status CSS
    app.js          - Main controller + auto-refresh + timeframes + visibility pause
    ws.js           - WebSocket client with auto-reconnect + tab-aware defer
    charts.js       - Chart.js chart management + theme re-theming
    api.js          - REST API client (all endpoints incl. feed status)
    ui.js           - UI rendering functions (freshness badges, decision data, feed status, agent UI)
```

### Dashboard Tabs
1. **Index** - Tariff Pressure Index + Shock Score + Macro Prediction + Macro Terminal (WITS series, rolling delta, country weights, correlation heatmap) + freshness badge + timeframe selector (1h/4h/1d/7d)
2. **Markets** - Multi-venue prices, funding, carry scores, microstructure, price integrity, Solana execution quality, funding arb, basis monitor, feed status panel (collapsible) + freshness badge
3. **Divergence** - Cross-venue spread analysis + dislocation alerts + freshness badge
4. **Stablecoins** - Peg monitor, depeg heatmap, stress/peg-break probability, flow momentum
5. **Strategy** - Rule evaluation results (5 rules), adaptive risk weights, portfolio proposal
6. **Execution** - Decision Data Status panel (pre-trade data quality), paper/live trades, positions, PnL attribution, Execution Quality Index
7. **Risk** - Stress tests, guardrails, Monte Carlo VaR/CVaR (minutes/hours/days), regime replay + analogs, liquidation heatmap
8. **Agents** - 6 AI agent signals with confidence badges, expandable reasoning, proposed actions, and registry

### Event Timeline (always visible)
Color-coded events: green=fills, red=errors, yellow=alerts, blue=info, purple=agents

## Phase 4 Features
- **Light/Dark Theme**: Toggle in header, persists in localStorage, Chart.js charts re-theme
- **Chart Timeframe Selectors**: 1h/4h/1d/7d buttons on Index chart
- **Auto-Refresh Toggle**: Header button to pause/resume 5s polling
- **Monte Carlo Time Units**: Minutes/Hours/Days selector with horizon conversion
- **Per-Panel Freshness Badges**: LIVE/FRESH/STALE/DEGRADED indicators with age
- **Data Feed Status Panel**: Collapsible panel showing all 7 data sources with status
- **JupiterAgent**: 6th agent monitoring quote freshness, route complexity, price impact, slippage risk, Solana congestion
- **Improved Agent UI**: Confidence badges, expandable reasoning, proposed action display
- **Decision Data Status**: Pre-trade panel showing data quality warnings in Execution tab
- **Macro Terminal Completeness**: WITS series, rolling delta, country weights, correlation heatmap
- **Performance Hardening**: visibilitychange pauses polling, WS message debouncing, tab-aware reconnect

## Key Design Decisions
- **Fail-open**: Missing API keys disable features, never crash
- **Paper mode default**: EXECUTION_MODE=paper until explicitly changed
- **Unified event bus**: All components write to single event log (40+ event types)
- **Price authority cascade**: Pyth → Kraken → CoinGecko with integrity validation
- **WebSocket-first frontend**: Primary updates via /ws/live, minimal polling
- **Heuristic agents**: Rule-based AI agents, not ML-dependent, deterministic
- **Portfolio proposals only**: Optimizer suggests allocations, never auto-trades
- **Performance-aware**: Hidden tab pauses polling, WS messages batched at 200ms

## Environment Variables
See `.env.example` for full list. Key ones:
- `DATABASE_URL` - PostgreSQL connection (auto-set by Replit)
- `REDIS_URL` - Redis connection (default: redis://localhost:6379)
- `EXECUTION_MODE` - paper|live (default: paper)
- `LOG_LEVEL` - INFO|DEBUG|WARNING (default: INFO)
- `ADAPTIVE_WEIGHTS` - 1|0 (default: 1, enable adaptive risk weighting)
- `HYPERLIQUID_API_KEY` - For live HL execution
- `SOLANA_PRIVATE_KEY` - For Drift/Jupiter execution
- `SOLANA_RPC_URL` - Solana RPC endpoint
- `MAX_LEVERAGE`, `MAX_MARGIN_USAGE`, `MAX_DAILY_LOSS` - Risk limits

## Running
```bash
python main.py
```
Starts FastAPI on port 5000 with Redis auto-start and ingest scheduler.

## Tests
```bash
pytest tests/
```
77 passing tests covering index calculation, shock detection, divergence alerts, risk throttling, basis engine, funding arb, stable flow, adaptive weights, portfolio optimizer, liquidation heatmap, execution metrics, and Solana liquidity.

## User Preferences
- Dark theme trading desk aesthetic (default, with light mode option)
- No React, vanilla JS + Chart.js only
- Structured logging (JSON format)

