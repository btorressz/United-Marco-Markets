# United Marco Markets Tariff Risk Desk — Codebase Guide


## Root

| File | Purpose |
|------|---------|
| `main.py` | Entry point. Starts Redis (if available), creates the FastAPI app, mounts static files at `/frontend`, applies database migrations, launches the ingest scheduler with 6 periodic jobs, and runs Uvicorn on port 5000. Registers 22 API routers (4 additional Phase 5B routers created but not yet registered). Serves `frontend/index.html` at the root `/` with no-cache headers. |
| `README.md` | Project metadata and architecture notes kept in sync as the project evolves. Always loaded into agent memory. |
| `summary.md` | Plain-English summary of the entire application for non-technical readers. |
| `codebase.md` | This file — detailed technical guide to every file in the codebase. |

---

## Backend (`backend/`)

The backend is a Python/FastAPI application organized into seven packages: `api`, `core`, `compute`, `agents`, `ingest`, `execution`, and `data`.

### `backend/config.py`

Centralized configuration loaded from environment variables with safe defaults. Defines:
- Execution mode (`EXECUTION_MODE`, default: `paper`)
- Risk limits (`MAX_LEVERAGE=3.0`, `MAX_MARGIN_USAGE=0.6`, `MAX_DAILY_LOSS=500`)
- WITS country list for tariff data
- API keys for Hyperliquid, Solana/Drift/Jupiter (all optional — fail-open)
- Logging level, database URL, Redis URL
- Adaptive weights toggle (`ADAPTIVE_WEIGHTS`, default: `1`)

### `backend/logging_config.py`

Configures structured JSON logging across the entire application. All log entries include ISO-8601 timestamp, level, logger name, and message. Exception tracebacks are included in the JSON payload.

---

### `backend/api/` — HTTP & WebSocket Routes

Each file is a FastAPI `APIRouter` mounted in `main.py`. Every router is self-contained with its own dependencies and fail-open error handling. 26 route files total (22 registered in main.py, 4 Phase 5B pending registration).

| File | Prefix | What it does |
|------|--------|--------------|
| `index_routes.py` | `/api/index` | Tariff Pressure Index latest value, history (with `?window=` support for 1h/4h/1d/7d), components breakdown, alerts, and the Macro Terminal endpoint returning tariff series, rolling delta, country weights, and correlation heatmap. |
| `markets_routes.py` | `/api/markets` | Multi-venue SOL/BTC/ETH prices from Pyth, Kraken, CoinGecko, Hyperliquid, and Drift. Also returns funding rates and price integrity check (cross-venue deviation in bps with per-feed timestamps). |
| `divergence_routes.py` | `/api/divergence` | Cross-venue spread analysis. Detects and alerts when the same asset trades at meaningfully different prices across venues. Returns spreads with venue pairs and dislocation alerts. |
| `stablecoin_routes.py` | `/api/stablecoins` | Stablecoin peg monitoring for USDC, USDT, DAI. Returns latest health (price, depeg bps, status), history, stress analysis, peg-break probability, and alerts. |
| `predict_routes.py` | `/api/predict` | ML-based macro prediction using a sigmoid model over 7 macro features (tariff index, shock score, rate of change, funding regime, vol regime, carry score, stablecoin health). Returns probability of BTC up in 4h with confidence and driver explanations. |
| `montecarlo_routes.py` | `/api/montecarlo` | Monte Carlo VaR/CVaR simulation engine. Accepts symbol, position size, horizon (in float hours), and number of paths (100-10,000). Returns VaR/CVaR at 95% confidence, mean PnL, and distribution histogram data. |
| `yield_routes.py` | `/api/yield` | Carry score calculations — converts periodic funding rates into annualized carry scores for yield comparison across venues. |
| `microstructure_routes.py` | `/api/microstructure` | Order book imbalance (buy vs sell pressure ratio), basis spread between spot and perp, and bid-ask spread analysis from Hyperliquid data. |
| `agents_routes.py` | `/api/agents` | Runs all 7 registered AI agents (Risk, Macro, Execution, Liquidity, Hyperliquid, Jupiter, Hedging) against current market state. Returns signals with confidence scores (0.70-0.95), severity, direction, proposed actions, reasoning, and data timestamps. Also exposes the agent registry with descriptions and status. Builds agent state from StateStore snapshots including prices, index, shock, funding, microstructure, positions, integrity, prediction probability, and carry score. |
| `rules_routes.py` | `/api/rules` | Evaluates the 5-rule strategy engine against current market state. Returns triggered actions (open_long, open_short, reduce, rotate_to_stables) with reasons. Exposes rule status listing and `/api/rules/adaptive-weights` for dynamic weight adjustment based on regime. |
| `execution_routes.py` | `/api/execution` | Order submission (routed through ExecutionRouter with risk checks), position listing (live + DB), paper trade history. Supports venue selection (paper, hyperliquid, drift). |
| `risk_routes.py` | `/api/risk` | Stress test scenarios (tariff_shock, liquidity_crisis, flash_crash, funding_flip), risk guardrail status (leverage, margin, daily loss), and `/api/risk/regime-analogs` returning historical regime outcome distribution (avg returns at 4h/24h/3d, win rates, sample count). |
| `events_routes.py` | `/api/events` | Event timeline — paginated query of all system events from the Postgres event log. Default limit 50 events, ordered by timestamp descending. |
| `health_routes.py` | `/api/health` | System health check returning DB connectivity, Redis status, scheduler state, execution mode, and version. Also exposes `/api/health/feeds` returning per-feed status for all 7 data sources (Pyth, Kraken, CoinGecko, Hyperliquid, Drift, WITS, GDELT) with name, last update timestamp, age in seconds, status (ok/warning/error/fallback), and whether each is authoritative. |
| `ws_routes.py` | `/ws/live` | WebSocket endpoint. Accepts client connections, subscribes them to the Redis pub/sub `desk:events` channel, and forwards all events in real-time. Sends a snapshot message on connect. Tracks connected client count. |
| `metrics_routes.py` | `/api/metrics` | Execution Quality Index (EQI) — returns composite score (0-100), latency p50/p95 in milliseconds, average slippage in bps, fill count, and anomaly list per venue. |
| `solana_routes.py` | `/api/solana` | Solana execution quality score (0-100), congestion detection (RPC latency + slot delta), slippage risk level (low/medium/high), and route depth estimation for Jupiter swaps. |
| `funding_arb_routes.py` | `/api/funding-arb` | Hyperliquid vs Drift funding rate arbitrage detection. Returns spread (bps), persistence duration, historical mean, arb signal direction (long_hl_short_drift / short_hl_long_drift / none), and expected net carry. |
| `basis_routes.py` | `/api/basis` | Perpetual basis monitor — HL perp vs Kraken spot, Drift perp vs Pyth oracle, and HL vs Drift perp spread. Returns annualized basis (bps), net carry (basis + funding diff), and execution feasibility score (0-100). |
| `stable_flow_routes.py` | `/api/stable-flow` | Stablecoin flow momentum — computes risk-on/off indicator from stablecoin dominance proxy and peg deviation stress. Returns momentum (-1 to 1), risk indicator, and explanatory drivers. |
| `portfolio_routes.py` | `/api/portfolio` | Portfolio construction optimizer. Supports `?method=risk_parity` (default), `mean_variance`, or `kelly`. Returns allocation weights across hl_perps, drift_perps, spot_jupiter, stablecoins with hard caps and floors. Includes reasoning for each allocation. Proposals only — never auto-trades. |
| `liquidation_routes.py` | `/api/liquidation` | Liquidation heatmap — leverage levels (1x, 2x, 3x, 5x, 7x, 10x) vs price drops (5%-50%) grid. Each cell contains liquidation probability computed from maintenance margin distance, vol-adjusted probability, and margin usage factor. Monotonicity enforced across both axes. |
| `sandbox_routes.py` | `/api/sandbox` | **[Phase 5B — created, not yet registered]** Strategy sandbox A/B comparison. POST `/run` accepts two strategy configurations and market state, returns side-by-side evaluation with triggered actions, VaR metrics, and recommendation. GET `/latest` returns last comparison. GET `/history` returns all past comparisons. |
| `replay_routes.py` | `/api/replay` | **[Phase 5B — created, not yet registered]** Event replay engine. POST `/run` accepts strategy config, event limit, and optional time range, replays events through the RulesEngine, returns summary with total actions, unique rules triggered, final portfolio value, and max drawdown. GET `/latest` returns last replay result. |
| `slippage_routes.py` | `/api/slippage` | **[Phase 5B — created, not yet registered]** Slippage model. GET `/latest` returns multi-venue slippage profiles (Hyperliquid, Jupiter, Drift) with curves and safe sizes. POST `/estimate` accepts venue and returns detailed slippage estimate with max safe order sizes at 10/25/50 bps thresholds. |
| `hedge_routes.py` | `/api/hedge` | **[Phase 5B — created, not yet registered]** Hedge ratio analysis. GET `/latest` returns full hedge analysis with correlations, hedge ratios, macro correlations, best hedge pair, and effectiveness. GET `/correlations` returns rolling correlation matrix. |

---

### `backend/core/` — Shared Infrastructure

| File | What it does |
|------|--------------|
| `models.py` | Pydantic models for internal data structures: `PriceTick` (symbol, price, source, confidence, timestamp), `FundingTick` (venue, market, rate, timestamp), `DivergenceAlert` (venues, spread_bps, severity), and others. Used for type safety across the system. |
| `schemas.py` | Pydantic response models for API endpoints: `IndexLatestResponse`, `RuleActionResponse`, `AlertResponse`, `StressTestResult`, `MonteCarloResult`, etc. Define the JSON shape of API responses. |
| `event_bus.py` | Unified event system with 59 defined event types. Emits events to both Redis pub/sub (channel `desk:events` for WebSocket broadcast) and Postgres (table `events` for persistence). All components write to this single bus. Event types include: `INDEX_UPDATE`, `SHOCK_SPIKE`, `DIVERGENCE_ALERT`, `FUNDING_REGIME_FLIP`, `RISK_THROTTLE_ON/OFF`, `RULE_ACTION_PROPOSED`, `ORDER_SENT/FILLED`, `SWAP_QUOTED/SENT`, `ERROR`, `STABLE_DEPEG_ALERT`, `STABLE_VOLUME_SPIKE`, `STABLE_FUNDING_SPIKE`, `STABLE_STRESS_ALERT`, `PEG_BREAK_PROB_UPDATE`, `PREDICTION_UPDATE/CONFIDENCE_LOW`, `MONTE_CARLO_RUN`, `RISK_VAR_BREACH`, `MICROSTRUCTURE_SIGNAL`, `DISLOCATION_ALERT`, `CARRY_UPDATE/REGIME_FLIP`, `AGENT_SIGNAL/ACTION_PROPOSED/BLOCKED`, `MACRO_TERMINAL_UPDATE`, `PRICE_DISLOCATION_ALERT`, `PNL_ATTRIBUTION_UPDATE`, `REGIME_MEMORY_UPDATE`, `EXECUTION_METRICS_UPDATE`, `SLIPPAGE_ANOMALY_ALERT`, `SOLANA_CONGESTION_WARNING`, `JUPITER_ROUTE_RISK`, `EXECUTION_THROTTLE`, `FUNDING_ARB_OPPORTUNITY/REGIME_FLIP`, `BASIS_UPDATE/OPPORTUNITY/FEASIBILITY_LOW`, `LIQUIDITY_THINNING_WARNING`, `STABLE_FLOW_UPDATE`, `ADAPTIVE_WEIGHTS_UPDATE`, `REGIME_ANALOG_MATCH`, `PORTFOLIO_PROPOSAL`, `LIQUIDATION_HEATMAP_UPDATE`, `JUPITER_QUOTE_STALE`, `JUPITER_SLIPPAGE_SPIKE`, `HEDGE_PROPOSAL`, `HEDGE_REBALANCE_SUGGESTED`, `HEDGE_THROTTLE_RECOMMENDED`, `SANDBOX_COMPARISON_RUN`, `REPLAY_COMPLETED`, `SLIPPAGE_MODEL_UPDATE`, `SAFE_SIZE_WARNING`, `HEDGE_RATIO_UPDATE`, `STABLECOIN_PLAYBOOK_TRIGGERED`. |
| `state_store.py` | Redis-backed snapshot store. Components write latest state (prices, index values, regime, microstructure, etc.) as keyed snapshots with configurable TTLs (e.g., `price:pyth:SOL_USD`, `index:latest`, `regime:latest`). Also provides throttle checking for rate-limited alerts and events — prevents the same alert from firing more than once per configurable interval. |
| `price_authority.py` | Price cascade logic implementing the Pyth → Kraken → CoinGecko fallback chain. Returns the best available price with source attribution. Falls back gracefully if the primary oracle is unavailable. |
| `price_validator.py` | Cross-venue price integrity checker. Computes pairwise deviations between all available price sources in basis points. Flags WARNING when deviation exceeds a configurable threshold (default 50bps). Emits throttled `PRICE_DISLOCATION_ALERT` events. Returns overall integrity status (OK/WARNING/CRITICAL) for the header badge. |
| `normalization.py` | Normalizes raw data from different venue APIs into consistent internal formats. Handles differences in field naming, timestamp formats, and data structures across Pyth, Kraken, CoinGecko, Hyperliquid, and Drift. |
| `timeutils.py` | UTC timestamp helpers and window-string parsing. Converts window strings like "1h", "4h", "1d", "7d" into seconds for database queries and chart data filtering. |

---

### `backend/compute/` — Pure Computation Modules

Stateless computation functions. No I/O — they take data in and return results. 27 modules total.

| File | What it computes |
|------|-----------------|
| `index_calc.py` | **Tariff Pressure Index** — weighted composite score (0–100) combining tariff rates from WITS, trade values, and news shock from GDELT. Country-specific weights ensure tariffs involving larger trading partners have proportionally more impact. |
| `shock_calc.py` | **GDELT Shock Score** — z-score of news tone and volume from GDELT data. Detects geopolitical shock spikes when negative news coverage exceeds historical norms. Handles empty data and edge cases gracefully. |
| `divergence.py` | **Cross-venue spread detection** — identifies when the same asset trades at meaningfully different prices across venues. Computes spreads in basis points, classifies severity, and generates dislocation alerts when spreads exceed configurable thresholds. |
| `regime.py` | **Regime classification** — categorizes current funding regime (positive/negative/neutral) based on funding rate magnitude and sign. Categorizes volatility regime (low/normal/high/extreme) based on price volatility metrics. Used by adaptive weights, risk engine, and agents. |
| `regime_memory.py` | **Regime persistence and outcome library** — stores and replays regime state transitions. Extended with `get_outcome_distribution()` that analyzes historical regime analogs and returns average returns at 4h/24h/3d horizons, win rates, and the best historical analog for the current regime pattern. |
| `carry_score.py` | **Annualized carry** — converts periodic funding rates (typically 8-hour cycles) into annualized carry scores for yield comparison across venues. Used by the strategy engine and carry display. |
| `rules_engine.py` | **5 configurable trading rules**: (1) tariff shock hedge — opens short or reduces exposure when tariff index spikes; (2) divergence arb — suggests cross-venue arb when prices diverge; (3) funding flip — shorts when funding is extremely positive; (4) vol regime scale — adjusts position sizing by volatility regime; (5) stable rotation — rotates into safer stablecoins when health deteriorates. Each rule returns proposed action (open_long, open_short, reduce, rotate_to_stables) with venue, market, side, size, and reason. |
| `risk_engine.py` | **Guardian** — enforces three hard risk limits: maximum leverage (default 3x), maximum margin usage (default 60%), and maximum daily loss (default $500). Detects position-reducing trades via `_is_reducing()` — sells against existing longs or buys against existing shorts bypass all constraints (throttle, leverage, margin, daily loss, cooldown) so you can always exit. Cooldown (300s) only enforced in live mode; paper mode has no cooldown. Accepts `execution_mode` parameter. Returns detailed violation reasons. |
| `stress_tests.py` | **4 scenario stress tests** — simulates (1) tariff escalation (correlated sell-off), (2) liquidity crisis (widened spreads, slippage), (3) flash crash (sudden 20-40% drop), (4) funding flip (carry reversal) against current positions. Returns total PnL impact, max drawdown, margin call status, and per-position breakdown. |
| `stablecoin_health.py` | **Stablecoin peg monitor** — computes depeg magnitude in basis points from $1.00, classifies peg status (ok/warning/depeg/critical), detects stress conditions from multi-signal analysis, and estimates peg-break probability using a composite of depeg severity, volume anomalies, and cross-stable correlations. |
| `macro_predictor.py` | **Sigmoid macro prediction** — 7-feature model that predicts macro environment direction. Features: tariff index, shock score, rate of change, funding regime, vol regime, carry score, stablecoin health. Uses logistic sigmoid to output probability of BTC upside in 4h. Returns probability, confidence, and per-feature driver explanations. |
| `monte_carlo.py` | **Monte Carlo engine** — runs up to 10,000 simulated price paths using geometric Brownian motion calibrated to recent volatility. Computes Value at Risk (VaR) and Conditional Value at Risk (CVaR) at 95% confidence level. Accepts float horizon in hours (supports sub-hour via minutes conversion). Returns VaR, CVaR, mean PnL, path count, and distribution histogram data for charting. |
| `microstructure.py` | **Market microstructure** — analyzes Hyperliquid orderbook data to compute: bid/ask imbalance ratio (buy vs sell pressure), basis between spot and perpetual prices, effective spread in bps, and liquidity depth. Used by agents and the microstructure display panel. |
| `stable_yield.py` | **Stablecoin yield** — calculates yield and carry opportunities in stablecoin markets. Compares lending rates, DEX LP yields, and funding rate carry across stablecoin pairs. |
| `pnl_attribution.py` | **PnL attribution** — breaks down position-level profit and loss into component factors: market move, funding paid/received, fees, and slippage. Provides per-position and aggregate attribution. |
| `execution_metrics.py` | **Execution Quality Index (EQI)** — tracks order→fill latency, quote→execution price delta, and expected vs realized slippage. Maintains rolling window of last 100 fills per venue. Computes p50/p95 latency, average slippage in bps, and detects slippage anomalies via z-score (>2σ flagged). Returns composite EQI score (0–100) with anomaly list. |
| `solana_liquidity.py` | **Solana liquidity intelligence** — computes execution quality score (0–100) from four sub-scores: spread, slippage risk, congestion, and route complexity. Detects congestion via simulated RPC latency and slot delta. Estimates Jupiter route depth and price impact. Returns quality score, congestion warning flag, slippage risk level (low/medium/high), and component breakdown. |
| `funding_arb.py` | **Funding arb detector** — compares Hyperliquid and Drift funding rates. Detects when spread exceeds configurable threshold (default 5bps). Tracks spread persistence (consecutive readings in same direction), historical mean over rolling 100-entry window. Returns arb signal direction (long_hl_short_drift / short_hl_long_drift / none), spread in bps, persistence count, and expected net carry annualized. |
| `basis_engine.py` | **Perp basis engine** — computes three basis spreads: (1) HL perp vs Kraken spot, (2) Drift perp vs Pyth oracle, (3) HL perp vs Drift perp. For each: annualized basis in bps, net carry (basis ± funding differential), and execution feasibility score (0–100) based on liquidity, spread, and position constraints. Rolling history of 200 entries. |
| `stable_flow.py` | **Stablecoin flow momentum** — computes risk-on/off indicator from: stablecoin dominance proxy (high = risk-off), peg deviation stress (depeg = risk-off), and volume signal approximation. Returns momentum value (-1 to +1), risk_on_off_indicator string, and list of human-readable driver explanations. |
| `adaptive_weights.py` | **Adaptive risk weighting** — dynamically adjusts predictor weights across four categories (macro, carry, microstructure, momentum) based on current regime signals. When shock is high, macro weight increases; when vol is extreme, microstructure weight increases; when funding is skewed, carry weight increases. Default equal weights (25% each). Toggled via `ADAPTIVE_WEIGHTS` env var (default on). Returns weights dict, adjustments list, and adaptive_enabled flag. |
| `portfolio_optimizer.py` | **Portfolio construction** — supports three methods: (1) risk_parity (default) — equalizes risk contribution across assets; (2) mean_variance — maximizes Sharpe ratio; (3) scaled Kelly — fractional Kelly criterion. Allocates across hl_perps, drift_perps, spot_jupiter, stablecoins. Hard caps (50%/50%/50%/80%) and floors (0%/0%/0%/5% stable minimum). Returns allocation dict summing to 1.0, method used, and reasoning array. Proposals only — never auto-executes. |
| `liquidation_heatmap.py` | **Liquidation heatmap** — computes leverage (1x, 2x, 3x, 5x, 7x, 10x) vs price drop (5%, 10%, 15%, 20%, 25%, 30%, 40%, 50%) grid. Each cell = liquidation probability derived from: maintenance margin distance at that leverage/drop combination, volatility-adjusted probability, and current margin usage factor. Monotonicity enforced across both axes (higher leverage = higher probability, larger drop = higher probability). Probabilities clamped to [0, 1]. |
| `strategy_sandbox.py` | **[Phase 5] Strategy sandbox** — A/B comparison engine for rule configurations. Accepts two strategy configurations (config_a, config_b) as RulesEngine parameter overrides. Runs both against the same market state snapshot. For each variant: evaluates all 5 rules, counts triggered actions by type, runs a quick Monte Carlo VaR estimate. Returns side-by-side comparison with triggered actions, rule counts, VaR at 95%, and a recommended variant (the one with fewer risky actions or better VaR). Stores latest and historical results in memory. |
| `replay_engine.py` | **[Phase 5] Replay engine** — deterministic event replay for backtesting. Takes a list of historical events (from the event log), optional time range filter, and strategy configuration. Replays events chronologically through the RulesEngine, recording at each step: timestamp, event type, triggered actions, portfolio state (value, positions). Produces summary: total events processed, total actions triggered, unique rules fired, final portfolio value, max drawdown, and per-step action log. Stores latest replay result in memory. |
| `slippage_model.py` | **[Phase 5] Slippage model** — builds slippage curves (bps vs order size in USD) for configurable size buckets (100, 500, 1k, 5k, 10k, 50k, 100k USD). Estimates slippage from: orderbook depth, spread, volatility, and recent fill history. Computes max safe order sizes for three thresholds: 10bps, 25bps, 50bps. Returns per-venue profiles with curve data, safe sizes, and freshness timestamp. Multi-venue function aggregates across Hyperliquid, Jupiter, and Drift. |
| `hedge_ratio.py` | **[Phase 5] Hedge ratio calculator** — computes rolling correlation, beta, and optimal hedge ratio between asset pairs over a configurable observation window (default 30, minimum 5). For each pair: Pearson correlation, OLS beta, hedge ratio (beta × correlation sign), hedge effectiveness (R²), and confidence level (high if R² > 0.6 and window ≥ 20, else medium/low). Also computes macro-to-crypto correlations if shock series provided. Returns full analysis with best hedge pair, recommended hedge ratio, and actionable text. Handles insufficient data gracefully with zero-valued defaults. |
| `stablecoin_playbook.py` | **[Phase 5] Stablecoin playbook** — formalized defensive action playbook for depeg scenarios. Evaluates stablecoin health data against four tiers: (1) monitor — depeg > 30bps, priority 1, low urgency; (2) reduce_exposure — depeg > 50bps or stress > 0.5, priority 2, medium urgency; (3) diversify — any depeg > 0 affecting 2+ stables, priority 3, medium urgency; (4) hedge — peg-break probability > 0.3, priority 4, high urgency; (5) emergency_exit — depeg > 100bps, priority 5, critical urgency. Returns prioritized action list with priority, urgency, description, affected stablecoins, and trigger conditions. |

---

### `backend/agents/` — Heuristic AI Agents

Seven rule-based agents that analyze market state and emit signals. Each agent follows the same interface: `evaluate(state: dict) -> list[dict]`. Each signal includes `agent` (name), `signal` (action text), `confidence` (0.0–1.0), `severity` (low/medium/high), `direction` (bullish/bearish/neutral), `proposed_action` (e.g., reduce_size, block_execution, hedge), `reason` (detailed explanation), `ts` (signal timestamp), and `data_ts_used` (timestamp of data the signal is based on). All agents are heuristic/rule-based — no ML models, fully deterministic and explainable.

| File | Agent | What it monitors |
|------|-------|-----------------|
| `risk_agent.py` | Risk Agent | Monitors liquidation distance, recommends throttle during high shock + high vol conditions, alerts on margin usage exceeding thresholds. Proposes `reduce_size` or `block_execution` actions. Confidence range 0.75-0.90. |
| `macro_agent.py` | Macro Agent | Detects tariff momentum acceleration (rising index rate of change), GDELT news shock spikes (shock > 0.5), and high tariff regime (index > 60). Proposes `reduce_exposure` or `hedge`. Confidence range 0.70-0.85. |
| `execution_agent.py` | Execution Agent | Pre-trade safety checks: validates spread width, liquidity depth, and price integrity before execution. Warns on high slippage (> 20bps), wide spreads, and price integrity failures. Can `block_execution` in live mode. Confidence range 0.75-0.90. |
| `liquidity_agent.py` | Liquidity Agent | Stablecoin depeg detection (any stable > 50bps from peg), extreme order book imbalance (> 0.7 ratio), and wide spread / thin liquidity warnings. Proposes `reduce_size` or `pause_trading`. Confidence range 0.70-0.85. |
| `hyperliquid_agent.py` | Hyperliquid Agent | HL-specific microstructure: orderbook imbalance direction and magnitude, spread compression (potential breakout), trade aggression patterns, and liquidity thinning below safety thresholds. Emits `MICROSTRUCTURE_SIGNAL` and `LIQUIDITY_THINNING_WARNING` events. Confidence range 0.70-0.90. |
| `jupiter_agent.py` | Jupiter Agent | Jupiter/Solana swap intelligence: quote freshness monitoring (stale quote > 30s), route complexity analysis (warns > 3 hops), price impact estimation (warns > 1%), slippage risk assessment, and Solana congestion detection (RPC latency, slot lag). Reuses `solana_liquidity.py` for congestion data. Emits `JUPITER_QUOTE_STALE` and `JUPITER_SLIPPAGE_SPIKE` events. Confidence range 0.70-0.95. |
| `hedging_agent.py` | Hedging Agent | **[Phase 5]** Position-aware hedge recommendations. Analyzes open positions against current shock level, vol regime, funding rates, and margin usage. Computes hedge urgency score (0–1) from weighted combination of signals. Proposes per-position actions: reduce_exposure (high shock + positions open), add_hedge (high vol + unhedged), rotate_to_stables (negative funding + large positions), or increase_size (low risk + favorable carry). Configurable thresholds for each signal dimension. Returns proposals with urgency scores, suggested hedge ratios, and detailed reasoning. |

---

### `backend/ingest/` — Data Ingestion

All ingest modules are fail-open — if an API is unreachable, returns an error, or a key is missing, the module logs a warning and returns gracefully. The scheduler continues running all other jobs. No single data source failure can crash the system.

| File | Data Source | Schedule | Details |
|------|------------|----------|---------|
| `scheduler.py` | APScheduler coordinator | — | Registers and runs all 6 ingest jobs on their configured intervals. Uses `BackgroundScheduler` with `default` executor. Logs job additions and completions. |
| `wits_ingest.py` | World Bank WITS API | Every 6 hours | Pulls tariff rate data by country and product category. Updates the state store with latest tariff data used by the Tariff Pressure Index. |
| `gdelt_ingest.py` | GDELT API | Every 5 minutes | Fetches news tone and volume data. Updates the state store with latest GDELT data used by the shock score calculator. |
| `kraken_ingest.py` | Kraken REST API | Every 30 seconds | Fetches spot prices for SOL, BTC, ETH via the Kraken ticker endpoint. Second in the price authority cascade. |
| `coingecko_ingest.py` | CoinGecko API | Every 60 seconds | Fetches fallback spot prices via CoinGecko's simple price endpoint. Third in the price authority cascade. |
| `pyth_ingest.py` | Pyth Network oracle | Every 30 seconds | Fetches on-chain oracle prices for SOL, BTC, ETH from the Pyth price feed API. First choice (most trusted) in the price cascade. |
| `drift_ingest.py` | Drift Protocol API | Every 60 seconds | Fetches perpetual market data (mark price, open interest) and funding rates for SOL-PERP from the Drift mainnet API. Requires authentication (may return 401 without valid credentials — handled gracefully). |
| `hyperliquid_ws.py` | Hyperliquid WebSocket | Real-time | Connects to Hyperliquid's WebSocket feed for real-time L2 orderbook updates and trade data. Used for microstructure analysis. |

---

### `backend/execution/` — Order Routing

| File | What it does |
|------|--------------|
| `router.py` | Central order router. Fetches live price from PriceAuthority cascade (Pyth→Kraken→CoinGecko) to fill orders without explicit price. Validates price freshness against `PRICE_FRESHNESS_THRESHOLD_S` (default 30s) — stale data blocks live trades, tags paper trades as DEGRADED. Checks price integrity — WARNING blocks live trades (configurable via `PRICE_INTEGRITY_BLOCK_LIVE`), tags paper trades. Passes `execution_mode` to risk engine so cooldown is paper-aware. Emits `TRADE_BLOCKED_STALE_DATA` and `TRADE_DEGRADED_DATA` events. Enriches all orders with data context (tariff_ts, shock_ts, price_ts, price_source, price_asof_ts, integrity_status, data_age_ms). Falls back to paper executor on any live execution failure. |
| `paper_exec.py` | Paper trading executor. Simulates fills instantly at current market price, tracks positions in memory with signed size (positive=long, negative=short). Position data includes `side` field ("long"/"short"). Emits `ORDER_SENT` and `ORDER_FILLED` events with full data context including `message`, `price_source`, `price_asof_ts`, `data_quality`. Supports position opening, closing, reducing, and flipping (long→short or short→long). |
| `hyperliquid_exec.py` | Hyperliquid REST executor for live trading. Requires `HYPERLIQUID_API_KEY` environment variable. Disabled (with warning log) if key is not set. |
| `drift_exec.py` | Drift Protocol executor for live Solana perpetual trading. Requires `SOLANA_PRIVATE_KEY`. Disabled if key is not set. |
| `jupiter_exec.py` | Jupiter aggregator for Solana token swaps. Fetches best route via Jupiter API, constructs and signs Solana transaction. Requires `SOLANA_PRIVATE_KEY` and `SOLANA_RPC_URL`. Disabled if credentials are not set. |
| `solana_tx.py` | Solana transaction construction and signing helper. Builds transaction objects, handles recent blockhash fetching, and signs with the configured private key. Used by both Drift and Jupiter executors. |

---

### `backend/data/` — Persistence Layer

| File | What it does |
|------|--------------|
| `db.py` | PostgreSQL connection pool management using psycopg2. Creates the pool on app startup (via `init_db()`), provides `get_conn()` context manager for borrowing connections, and closes the pool on app shutdown. Runs migrations from `migrations.sql` on initialization. |
| `migrations.sql` | SQL schema defining 8 tables: `index_snapshots` (tariff index history), `events` (unified event log), `market_ticks` (price data), `funding_snapshots` (funding rate history), `positions` (open position tracking), `orders` (order history), `regime_snapshots` (regime state history), `stablecoin_ticks` (stablecoin price/peg history). All tables use `IF NOT EXISTS` for idempotent migrations. |

### `backend/data/repositories/` — CRUD Repositories

| File | Table(s) | Operations |
|------|----------|------------|
| `index_repo.py` | `index_snapshots` | Insert index snapshots with all component values, query latest snapshot, query history by time window (supports 1h/4h/1d/7d). |
| `events_repo.py` | `events` | Insert events with type, source, payload (JSONB), and timestamp. Query by type and/or time range. Paginated listing for the timeline (default limit 50, ordered by timestamp descending). |
| `market_repo.py` | `market_ticks`, `funding_snapshots` | Insert price ticks with venue, symbol, price, and source. Insert funding snapshots with venue, market, and rate. Query latest ticks by venue and symbol. |
| `positions_repo.py` | `positions`, `orders` | Insert/update positions (open, close, adjust size). Insert orders with full execution details. Query open positions. Query order history. |

---

## Frontend (`frontend/`)

Vanilla HTML/CSS/JS single-page application with Chart.js for charting. No build step, no framework, no React. Served as static files from the `/frontend` mount point with the HTML shell at `/`.

### `frontend/index.html`

The single-page shell containing:

**Header bar:**
- App name ("Tariff Risk Desk") with diamond accent
- Database connectivity indicator (green/red dot + "DB")
- Version badge ("v0.1.0")
- Price integrity badge ("Price: OK" / "Price: WARNING")
- Auto-refresh toggle button ("AUTO" with pulsing green dot / "PAUSED")
- Light/dark theme toggle (SVG moon/sun icons with "DARK"/"LIGHT" label)
- WebSocket connection indicator ("LIVE" green / "OFFLINE" red)

**8 tab buttons:** Index, Markets, Divergence, Stablecoins, Strategy, Execution, Risk, Agents

**Tab content panels (hidden/shown via JS):**

1. **Index tab:** Tariff Index / Shock Score / Rate of Change / Last Updated metric cards. Index & Shock History dual-axis chart with freshness badge and timeframe selector (1h/4h/1d/7d). Index Components table. Macro Prediction panel (BTC up probability, confidence, drivers). Macro Terminal section with four sub-panels: WITS Tariff Series, Rolling Delta, Country Weights, Correlation Heatmap — each with empty-state fallbacks.

2. **Markets tab:** Multi-venue price table (symbol, source, price, confidence, time) with freshness badge. Funding rates bar chart. Carry scores panel. Microstructure section: OB Imbalance, Basis Opportunity, Price Integrity (3-column grid). Solana Execution Quality section: Quality Score, RPC Latency, Route Info (3-column grid). Funding Arbitrage panel (signal, spread, persistence, net carry). Basis Monitor panel (HL-spot, Drift-spot, HL-Drift spread, annualized basis, net carry). Data Feed Status panel (collapsible via Show/Hide button, 7-source status table).

3. **Divergence tab:** Cross-venue spread chart with freshness badge. Spread Details table (market, venue A/B, prices, spread). Divergence Alerts list. Dislocation Alerts list.

4. **Stablecoins tab:** USDC/USDT/DAI peg status metric cards (price, depeg bps). Depeg heatmap table. Stress / Peg Break probability panel. Stablecoin Alerts list. Stable Flow Momentum panel (momentum value, risk-on/off indicator, drivers).

5. **Strategy tab:** Active Rule Signals list (rule cards with action badges). Registered Rules list. Adaptive Risk Weights panel (per-predictor weight bars, adaptive on/off, adjustments). Portfolio Proposal panel (method, allocation bars with percentages, reasoning).

6. **Execution tab:** Decision Data Status panel (system health, price integrity, tariff index freshness with warnings). Submit Paper Order form (venue, market, side, size, price). Open Positions table (venue, market, side, size, entry price, time). PnL Attribution panel. Execution Quality Index panel (EQI score, latency p50/p95, avg slippage, fill count, anomalies). Paper Trade History table (venue, market, side, size, price, status, time).

7. **Risk tab:** Throttle banner (active/inactive with reason). Leverage / Margin Usage / Daily PnL metric cards. Guardrails panel (max leverage, max margin, max daily loss, cooldown, execution mode). Stress Test form (4 scenarios) with results panel. Monte Carlo form (symbol, position size, horizon value, time unit selector, paths) with VaR/CVaR results and distribution chart. Regime Replay panel (avg 4h/24h returns, win rate, sample count). Liquidation Heatmap (color-coded HTML table: green→yellow→red).

8. **Agents tab:** Agent Status row (active agents count = 7, active signals, last updated). Agent Signals container (cards with severity/direction/confidence badges, expandable reasoning, proposed actions, timestamps). Agent Registry (list of all agents with name, status, description).

**Event Timeline** (always visible at bottom): Timestamp, event type badge, message, source. Color-coded: green=fills, red=errors, yellow=alerts, blue=info. Shows last 50 events.

### `frontend/assets/styles.css`

Dual-theme trading desk CSS using CSS custom properties:

- **Dark theme (default):** Dark backgrounds (`#0d1117`, `#161b22`, `#1c2333`), light text (`#e6edf3`), accent colors (green `#3fb950`, red `#f85149`, blue `#58a6ff`, yellow `#e3b341`, purple `#bc8cff`, cyan `#39d2c0`).
- **Light theme** (`[data-theme="light"]`): Institutional light backgrounds (`#f6f8fa`, `#ffffff`, `#f0f3f6`), dark text (`#1f2328`), adjusted accent colors for readability.
- Components: metric cards, tables, tab system, chart containers, event timeline, status badges (connected/disconnected with pulse animation), freshness badges (LIVE green/FRESH blue/STALE yellow/DEGRADED red/NO DATA gray), feed status panel, timeframe selector buttons, auto-refresh toggle, decision data panel, agent signal cards with confidence badges, liquidation heatmap color scale, scrollbar theming.

### `frontend/assets/app.js`

Main application controller (443 lines):

- **Initialization:** Runs on `DOMContentLoaded`. Sets up theme, tabs, charts, WebSocket, forms, feed status toggle, auto-refresh, timeframe selectors, and visibility listener. Starts 5-second polling interval.
- **Theme system:** Reads saved theme from localStorage (default: dark). Applies `data-theme="light"` attribute on `<html>`. Toggles SVG moon/sun icons and DARK/LIGHT label. Triggers Chart.js re-theming via `Charts.reThemeAllCharts()` with 50ms delay.
- **Auto-refresh:** Toggle pauses/resumes the 5s polling cycle. Shows pulsing green dot + "AUTO" when active, "PAUSED" when disabled.
- **Timeframe selectors:** 1h/4h/1d/7d buttons on charts. Passes selected window parameter to history API calls. Stores per-chart selection.
- **MC time units:** Minutes/Hours/Days selector converts to hours for backend. Displays human-readable summary ("Horizon: 15 minutes").
- **Tab switching:** Shows/hides panels, triggers immediate data fetch for activated tab.
- **Periodic polling:** 5s interval calls `refresh()` which fetches health, timeline, and active tab data. Skipped when `autoRefresh=false` or tab is hidden.
- **Tab refresh functions:** Each tab uses `Promise.allSettled()` to fetch all data sources in parallel:
  - Index: latest, history (with timeframe), components, prediction, macro terminal
  - Markets: prices, funding, carry, microstructure, integrity, solana quality, funding arb, basis, feed status
  - Divergence: spreads, alerts
  - Stablecoins: health, alerts, stable flow
  - Strategy: rules evaluation, rules status, adaptive weights, portfolio proposal
  - Execution: positions, paper trades, EQI, integrity, health, index data (for decision panel)
  - Risk: status, guardrails, liquidation heatmap, regime analogs
  - Agents: signals, registry
- **Performance:** `visibilitychange` listener pauses polling when tab is hidden. WebSocket messages buffered in array, flushed every 200ms to prevent DOM thrashing. Tab-aware WS reconnect deferral.
- **Forms:** Order submission, stress test, and Monte Carlo forms with loading states and error handling.

### `frontend/assets/api.js`

REST API client (92 lines). Thin wrapper around `fetch()` with error handling. Two base methods: `fetchJSON(path)` for GET and `postJSON(path, body)` for POST. All endpoints exposed as named functions:

- Index: `getIndexLatest()`, `getIndexHistory(window)`, `getIndexComponents()`, `getMacroTerminal()`
- Markets: `getMarketLatest()`, `getMarketHistory(venue, window)`, `getFunding()`, `getIntegrity()`, `getCarry()`, `getMicrostructure()`
- Stablecoins: `getStablecoinHealth()`, `getStablecoinAlerts()`, `getStableFlow()`
- Strategy: `getRulesEvaluation()`, `getRulesStatus()`, `getAdaptiveWeights()`, `getPortfolioProposal(method)`
- Execution: `getPositions()`, `getPaperTrades()`, `postOrder(order)`
- Risk: `getRiskStatus()`, `getGuardrails()`, `postStressTest(scenario)`, `postMonteCarlo(params)`, `getRegimeAnalogs()`, `getLiquidationHeatmap()`
- Agents: `getAgentSignals()`, `getAgentRegistry()`
- Prediction: `getPrediction()`
- Events: `getEvents(limit)`
- Health: `getHealth()`, `getFeedStatus()`
- Metrics: `getEQI()`, `getSolanaQuality()`, `getSolanaCongestion()`
- Phase 3: `getFundingArb()`, `getBasisLatest()`, `getBasisFeasibility()`

### `frontend/assets/ui.js`

UI rendering module (961 lines). One rendering function per tab/section:

- `renderIndexTab(data)` — Renders tariff index, shock score, rate of change metric cards. Updates index chart via Charts.updateChart(). Renders macro prediction panel (probability, confidence, drivers). Renders macro terminal (WITS series, rolling delta, country weights, correlation heatmap) with empty-state fallbacks. Updates freshness badge.
- `renderMarketsTab(data)` — Renders multi-venue price table rows. Updates funding chart. Renders carry score panels. Renders microstructure metrics (OB imbalance, basis info, integrity detail). Renders Solana quality cards (score with color coding, RPC latency, congestion, route info). Renders funding arb metric row (signal badge, spread, persistence, net carry). Renders basis monitor (HL-spot, Drift-spot, HL-Drift spread, annualized basis, net carry). Updates freshness badge and price integrity header badge.
- `renderFeedStatus(data)` — Renders collapsible data feed status table with per-source rows (name, status badge, age, last update timestamp, authoritative flag). Summary line with healthy/total count.
- `renderDivergenceTab(data)` — Renders spread chart, spread details table, divergence alerts, and dislocation alerts. Updates freshness badge.
- `renderStablecoinsTab(data)` — Renders USDC/USDT/DAI metric cards with price and depeg bps. Renders depeg heatmap table, stress panel, alerts list, and stable flow momentum panel (momentum, risk-on/off indicator, drivers).
- `renderStrategyTab(data)` — Renders rule evaluation cards with action type badges (color-coded). Renders registered rules list. Renders adaptive weights panel with per-predictor percentage bars and adjustment notes. Renders portfolio proposal with method, allocation bars, and reasoning.
- `renderExecutionTab(data)` — Renders positions table, trade history table, and EQI panel (score, latency, slippage, anomalies).
- `renderDecisionDataPanel(data)` — Pre-trade data quality panel showing system health status, price integrity status, tariff index timestamp, and overall data quality assessment with color-coded warning levels.
- `renderRiskTab(data)` — Renders throttle banner (active/inactive). Renders leverage/margin/PnL metrics. Renders guardrail rows. Renders stress test results (PnL impact, max drawdown, margin call status). Renders MC results via `renderMCResult()`. Renders liquidation heatmap as color-coded HTML table (green < 20%, yellow 20-50%, orange 50-80%, red > 80%). Renders regime analog outcomes (avg returns, win rate, sample count).
- `renderMCResult(mc)` — Renders VaR/CVaR/mean PnL metrics. Updates MC distribution chart.
- `renderAgentsTab(data)` — Renders agent signal cards with: agent name badge (purple), severity badge (green/yellow/red), direction badge (green=bullish/red=bearish/blue=neutral), proposed action badge (red=block/yellow=reduce/blue=other), confidence percentage badge (color-coded). Expandable reasoning section (click to toggle). Data timestamps (signal time, data time). Renders agent registry with name, status badge, and description.
- `renderFreshnessBadge(elementId, timestamp)` — Reusable freshness indicator: LIVE (green, < 10s), FRESH (blue, < 60s), STALE (yellow, < 300s), DEGRADED (red, > 300s), NO DATA (gray, no timestamp).
- `renderTimeline(events)` / `addEventToTimeline(event, isNew)` — Color-coded event timeline rendering. Event classification: fills=green, errors=red, alerts=yellow, trades=blue, info=default. Caps at 50 events. New events animate in.
- `updateConnectionStatus(connected)` — Updates header LIVE/OFFLINE badge.
- Helper functions: `formatTimestamp()`, `formatNumber()`, `formatPrice()`, `classForValue()`.

### `frontend/assets/charts.js`

Chart.js chart management:
- `createIndexChart(canvasId)` — Dual-axis line chart: Tariff Index (left Y, blue) and Shock Score (right Y, red).
- `createFundingChart(canvasId)` — Bar chart for funding rates across venues.
- `createDivergenceChart(canvasId)` — Line chart for cross-venue spreads over time.
- `createMCChart(canvasId)` — Bar chart/histogram for Monte Carlo simulation PnL distribution.
- `updateChart(chart, data)` — Efficient data update without full chart recreation.
- `getThemeColors()` — Reads CSS custom properties at runtime to get current theme colors for chart elements (grid, ticks, tooltips, legends).
- `reThemeAllCharts()` — Updates all chart instances with current theme colors. Called after theme toggle with 50ms delay to allow CSS variable cascade.

### `frontend/assets/ws.js`

WebSocket client (115 lines):
- Connects to `/ws/live` (auto-detects ws/wss protocol from page protocol).
- Automatic reconnection with exponential backoff (1s → 2s → 4s → ... → 30s max, 10 attempts max).
- Tab-aware reconnect: defers reconnection when browser tab is hidden to save resources.
- Event dispatch system: handlers registered via `on(type, fn)`, removed via `off(type, fn)`.
- Message queue: buffers messages received before handlers are registered, flushes on reconnect.
- Connection state tracking: `isConnected()` for external queries.
- `send(data)` for sending messages to server (JSON stringified).

---

## Tests (`tests/`)

98 tests across 6 test files, all passing:

| File | Tests | What it covers |
|------|-------|----------------|
| `test_index_calc.py` | 6 | Tariff Pressure Index calculation — weighted composition from tariff rates and trade values, edge cases (empty data, zero weights), boundary values (0 and 100). |
| `test_shock_calc.py` | 16 | GDELT shock score — z-score computation from news tone/volume, spike detection at various thresholds, empty data handling, single-article edge cases, historical baseline comparison. |
| `test_divergence_alerts.py` | 14 | Cross-venue divergence — spread calculation between venue pairs, alert triggering at configurable thresholds, multi-venue scenarios (3+ venues), zero-spread cases, same-price no-alert verification. |
| `test_risk_throttle.py` | 18 | Risk engine constraints — leverage limit enforcement, margin cap enforcement, daily loss enforcement, combined violations, throttle activation/deactivation, cooldown enforcement (live mode only), cooldown skipped (paper mode), throttle allows position-reducing trades, edge cases. |
| `test_new_features.py` | 25 | Phase 3 features — basis engine, funding arb, stable flow, adaptive weights, portfolio optimizer, liquidation heatmap, execution metrics, Solana liquidity. |
| `test_paper_trading.py` | 19 | Paper trading — BUY creates long, SELL creates short, SELL reduces/closes/flips long, BUY closes short, events emitted for both sides, position `side` field ("long"/"short"), risk engine reducing detection, throttle/daily-loss bypass for reduces, no cooldown in paper mode. |

---

## Data Flow

```
External APIs (WITS, GDELT, Kraken, CoinGecko, Pyth, Drift, Hyperliquid)
        │
        ▼
   ingest/ (6 scheduled jobs, all fail-open)
        │
        ▼
   core/state_store (Redis snapshots with TTLs)
        │
        ├──► core/event_bus (Redis pub/sub + Postgres event log, 59 event types)
        │         │
        │         ▼
        │    ws_routes.py (WebSocket broadcast to connected clients)
        │         │
        │         ▼
        │    Frontend (real-time event timeline updates)
        │
        ▼
   compute/ (27 pure calculation modules, no I/O)
        │
        ▼
   api/ (26 REST endpoint routers)
        │
        ├──► Frontend (5s polling per active tab, Promise.allSettled parallel fetch)
        │
        ▼
   agents/ (7 heuristic AI agents evaluate state → emit signals)
        │
        ▼
   execution/router (risk check → agent pre-trade check → paper/live fill)
        │
        ▼
   data/repositories (Postgres persistence: index, events, ticks, positions, orders)
```

---

## Phase Summary

| Phase | Focus | Key Additions |
|-------|-------|---------------|
| 1 | Core platform | Tariff index, shock score, multi-venue prices, divergence, stablecoins, 5 rules, risk engine, stress tests, paper execution, event bus, WebSocket, 8-tab dashboard |
| 2 | Extended analytics | Monte Carlo VaR/CVaR, macro predictor, regime classification, PnL attribution, microstructure analysis |
| 3 | Market intelligence | EQI, Solana liquidity, funding arb, basis engine, stable flow, adaptive weights, portfolio optimizer, liquidation heatmap, regime memory |
| 4 | UX polish | Light/dark theme, chart timeframes, auto-refresh, MC time units, freshness badges, feed status, JupiterAgent, improved agent UI, decision data panel, macro terminal, performance hardening |
| 5 | Advanced backend | HedgingAgent, strategy sandbox, replay engine, slippage model, hedge ratio calculator, stablecoin playbook |
| 5B | Integration (in progress) | API routes for sandbox/replay/slippage/hedge created, HedgingAgent activated in agent pipeline, new event types added — frontend integration and route registration pending |

