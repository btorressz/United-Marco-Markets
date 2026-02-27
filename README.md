# United-Marco-Markets (Tariff Risk Desk)

# Overview
This project is a unified macro-to-markets risk desk designed to transform trade policy and geopolitical signals into actionable market intelligence. It monitors global tariff data and news sentiment to create a Tariff Pressure Index, integrates with live crypto market data from multiple sources, employs heuristic AI agents for risk analysis, and provides execution capabilities across various platforms. The system prioritizes safety with a default paper mode and a fail-open design, all presented through a dark/light theme trading desk dashboard.

## User Preferences
- Dark theme trading desk aesthetic (default, with light mode option)
- No React — vanilla JS + Chart.js only
- Structured logging (JSON format)
- Fail-open, never crash
- Paper mode by default

## System Architecture

### Core Design Principles
The system is built on a fail-open philosophy, where missing API keys or unavailable data sources disable features without crashing the system. It defaults to paper mode for execution, ensuring no real money is at risk unless explicitly configured. A unified event bus, utilizing Redis pub/sub and PostgreSQL persistence, centralizes all system events. Price data integrity is maintained through a cascading authority model (Pyth → Kraken → CoinGecko) with cross-venue validation. The frontend is WebSocket-first for live updates, complemented by 5-second REST polling. Heuristic, rule-based AI agents provide deterministic and explainable insights, with portfolio optimizers offering proposals rather than autonomous trading. Performance is optimized through mechanisms like pausing polling on hidden tabs and batching WebSocket messages.

### Backend (Python/FastAPI)
The backend is a FastAPI application serving as the primary API. It includes a comprehensive set of API routers for diverse functionalities such as tariff index data, market data, divergence analysis, stablecoin monitoring, predictive analytics, risk management (VaR/CVaR), execution, and agent signals. Shared infrastructure components handle data models, API schemas, event management, state storage, price validation, and data normalization. A `compute` layer houses numerous stateless modules for calculations like the Tariff Pressure Index, shock scores, divergence detection, regime classification, carry scores, and risk engine logic. Heuristic AI agents (e.g., risk, macro, execution, liquidity) provide analytical signals. Data ingestion is managed by an APScheduler-based system, fetching data from sources like World Bank WITS, GDELT, Kraken, CoinGecko, Pyth, Drift, and Hyperliquid. Execution routing supports both paper trading and live execution via Hyperliquid, Drift, and Jupiter. PostgreSQL is used for persistence, storing index snapshots, event logs, market ticks, and position data.

### Frontend (Vanilla HTML/CSS/JS + Chart.js)
The frontend is a single-page application with an 8-tab dashboard. It features a dark/light trading desk theme and utilizes vanilla HTML, CSS, and JavaScript with Chart.js for data visualization. Key functionalities include:
- **Dashboard Tabs**:
    - **Index**: Tariff Pressure Index, Shock Score, Macro Prediction, Macro Terminal.
    - **Markets**: Multi-venue prices, funding, carry scores, microstructure, price integrity.
    - **Divergence**: Cross-venue spread analysis and dislocation alerts.
    - **Stablecoins**: Peg monitor, depeg heatmap, stress/peg-break probability.
    - **Strategy**: Rule evaluation, adaptive risk weights, portfolio proposals.
    - **Execution**: Decision data status, paper/live trades, positions, PnL attribution, Execution Quality Index.
    - **Risk**: Stress tests, guardrails, Monte Carlo VaR/CVaR, regime analysis, liquidation heatmap.
    - **Agents**: AI agent signals with confidence badges, reasoning, and proposed actions.
- **Event Timeline**: Always visible, color-coded event log (last 50 events).
- **UI/UX Features**: Light/dark theme toggle, chart timeframe selectors, auto-refresh toggle, Monte Carlo time unit selector, per-panel freshness badges, and a collapsible data feed status panel.

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
- Structured logging (JSON format)

