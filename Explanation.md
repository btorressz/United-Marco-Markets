# United Marco Markets (Tariff Risk Desk) — Full Project Explanation

## What Is This?

The United Marco Markets(Tariff Risk Desk) is a real-time trading intelligence platform that connects two worlds that don't usually talk to each other: **global trade policy** (tariffs, sanctions, trade wars) and **cryptocurrency markets** (Bitcoin, Solana, Ethereum, stablecoins). The core idea is that when governments impose tariffs or trade tensions escalate, it creates ripple effects across financial markets — including crypto. This system detects those signals early and helps traders respond.

Think of it as a command center that watches the news, monitors prices across multiple exchanges, runs risk calculations, and tells you what's happening — all in one dashboard.


**NOTE** This project is for research and development purposes ONLY at the moment. 

---


## The Big Picture

The system works in five stages:

```
1. COLLECT  →  2. ANALYZE  →  3. DECIDE  →  4. EXECUTE  →  5. MONITOR
   (Data)        (Compute)      (Agents)      (Trading)      (Dashboard)
```

### Stage 1: Collect Data

Seven data feeds run continuously in the background, pulling information from around the world:

- **World Bank WITS** (every 6 hours) — Official tariff rates between countries. When the US raises tariffs on Chinese goods, this data updates.
- **GDELT** (every 5 minutes) — A massive news monitoring system that tracks global media. The system watches for articles mentioning tariffs, trade wars, sanctions, and import duties, then measures how negative or alarming the coverage is.
- **Pyth Network** (every 30 seconds) — An on-chain oracle that provides institutional-grade price data. This is the most trusted price source.
- **Kraken** (every 30 seconds) — A major cryptocurrency exchange. Provides spot prices as a backup to Pyth.
- **CoinGecko** (every 60 seconds) — A crypto data aggregator. Third-choice backup for prices.
- **Drift Protocol** (every 60 seconds) — A Solana-based decentralized exchange for perpetual futures. Provides funding rates and mark prices.
- **Hyperliquid** (real-time WebSocket) — A high-performance crypto exchange. Provides live orderbook data, trade flow, and funding rates.

Every single one of these feeds is **fail-open**: if any API goes down, returns errors, or has missing credentials, the system keeps running. Features that depend on that data simply show "no data" instead of crashing. This is a core design principle — the desk should never go dark.


### Stage 2: Analyze (The Compute Layer)

Raw data flows into 27 stateless calculation modules. Each one takes data in and produces a result — no side effects, no database writes, just pure math. Here are the key ones:

**Tariff Pressure Index (0–100)**
The headline number. Combines tariff rate data from WITS with news shock from GDELT into a single score. A reading of 20 means trade tensions are calm. A reading of 80 means tariffs are spiking and the news is full of trade war headlines. The index is weighted by trade volume — tariffs between the US and China matter more than tariffs between two small economies.

**Shock Score**
A z-score of GDELT news data. Measures how unusual current trade coverage is compared to historical norms. A shock score above 0.5 means something abnormal is happening in trade policy news.

**Cross-Venue Divergence**
When Bitcoin trades at $50,000 on Kraken but $50,150 on Hyperliquid, that 30-basis-point gap is a divergence. The system tracks these gaps across all venue pairs and alerts when they exceed configurable thresholds. Large divergences can signal market stress or arbitrage opportunities.

**Price Authority Cascade**
Not all price sources are equally trustworthy. The system uses a hierarchy: Pyth (most trusted, on-chain oracle) → Kraken (established exchange) → CoinGecko (aggregator). When you need "the price" of an asset, it checks Pyth first. If Pyth is unavailable, it falls back to Kraken, then CoinGecko. Every price comes tagged with its source and timestamp.

**Price Integrity Validation**
Compares prices across all available sources. If Pyth says SOL is $150 but Kraken says $145, that's a 333-basis-point deviation — something might be wrong. The system flags this as a WARNING and can block live trades until prices converge.

**Regime Classification**
Categorizes the current market environment along two dimensions:
- **Funding regime** (positive/negative/neutral) — Are traders paying to be long or short?
- **Volatility regime** (low/normal/high/extreme) — How much are prices moving?

These regime labels drive adaptive behavior throughout the system.

**Macro Prediction**
A sigmoid-based model that takes 7 features (tariff index, shock score, rate of change, funding regime, vol regime, carry score, stablecoin health) and outputs a probability of BTC going up in the next 4 hours. It also explains which features are driving the prediction and how confident it is.

**Monte Carlo VaR/CVaR**
Runs up to 10,000 simulated price paths using geometric Brownian motion to estimate:
- **Value at Risk (VaR)** — "There's a 95% chance you won't lose more than $X"
- **Conditional VaR (CVaR)** — "If you do lose more than VaR, the average loss would be $Y"

Supports horizons in minutes, hours, or days.


**Stablecoin Health Monitor**
Tracks USDC, USDT, and DAI against their $1.00 peg. Measures depeg in basis points, detects stress conditions, and estimates peg-break probability. When stablecoins start depegging, it's often an early warning of broader market stress.

**Liquidation Heatmap**
A grid showing liquidation probability at different leverage levels (1x through 10x) and price drops (5% through 50%). Shows traders exactly how dangerous their leverage is across scenarios.

**Portfolio Optimizer**
Proposes allocation weights across four categories: Hyperliquid perpetuals, Drift perpetuals, Jupiter spot swaps, and stablecoins. Supports three methods:
- **Risk Parity** — Equalize risk contribution across assets
- **Mean-Variance** — Maximize risk-adjusted returns (Sharpe ratio)
- **Kelly Criterion** — Mathematically optimal bet sizing

The optimizer only proposes — it never auto-trades.

**Additional Modules:**
- Funding rate arbitrage detection (Hyperliquid vs Drift)
- Perpetual basis engine (annualized basis, net carry, feasibility scoring)
- Stablecoin flow momentum (risk-on/risk-off indicator)
- Adaptive risk weights (dynamically adjust strategy weights by regime)
- Execution Quality Index (tracks latency, slippage, and fill quality)
- Solana liquidity intelligence (congestion detection, route quality)
- Strategy sandbox (A/B comparison of trading strategies)
- Replay engine (backtest strategies against historical events)
- Slippage model (estimate slippage curves and safe order sizes)
- Hedge ratio calculator (optimal hedge ratios between asset pairs)
- Stablecoin playbook (tiered defensive actions for depeg scenarios)

### Stage 3: Decide (The Agent Layer)

Seven AI agents continuously evaluate market conditions and produce signals. They are **heuristic** — rule-based, not machine learning — which makes them deterministic, explainable, and predictable. Each agent specializes in a different domain:

**Risk Agent**
Watches liquidation distance and margin usage. When shock is high AND volatility is extreme, recommends throttling new trades. Proposes `reduce_size` or `block_execution`.

**Macro Agent**
Monitors tariff momentum (is the index accelerating?), GDELT shock spikes, and high-tariff regimes. When the tariff index exceeds 60, it recommends reducing exposure.

**Execution Agent**
Pre-trade safety checks. Before any order goes through, it validates spread width, liquidity depth, and price integrity. In live mode, it can outright block trades if conditions are unsafe.

**Liquidity Agent**
Watches for stablecoin depegging, extreme orderbook imbalance, and thin liquidity. If USDC depegs by more than 50 basis points, it recommends pausing trading.

**Hyperliquid Agent**
Specialized in Hyperliquid's orderbook microstructure. Detects imbalance direction, spread compression (potential breakout signal), trade aggression patterns, and liquidity thinning.

**Jupiter Agent**
Monitors Jupiter/Solana swap conditions: quote freshness (stale quotes are dangerous), route complexity (more hops = more risk), price impact estimation, and Solana network congestion.

**Hedging Agent**
Position-aware. Looks at your actual open positions and evaluates them against current shock, volatility, and funding conditions. Produces per-position hedge proposals with urgency scores and specific actions (reduce, hedge, rotate, increase).

Each agent emits signals with:
- **Confidence** (0.0 to 1.0) — How sure the agent is
- **Severity** (low/medium/high) — How urgent the signal is
- **Direction** (bullish/bearish/neutral) — Market direction assessment
- **Proposed action** — What to do about it (reduce_size, hedge, block_execution, etc.)
- **Reasoning** — Human-readable explanation of why

### Stage 4: Execute (The Trading Layer)

The execution router handles all trade requests through a multi-step safety pipeline:

```
Order Request
    ↓
[1] Fetch live price from Pyth → Kraken → CoinGecko cascade
    ↓
[2] Validate price freshness (must be < 30 seconds old)
    ↓
[3] Validate price integrity (cross-venue deviation check)
    ↓
[4] Risk engine check (leverage, margin, daily loss limits)
    ↓
[5] Execution agent pre-trade check (live mode only)
    ↓
[6] Route to executor (paper or live)
    ↓
[7] Emit ORDER_SENT → fill → emit ORDER_FILLED
```

**Paper Mode (Default)**
No real money is ever at risk unless you explicitly set `EXECUTION_MODE=live`. Paper mode simulates fills instantly at market price, tracks positions in memory, and records everything to the database. You can BUY to open longs and SELL to open shorts, reduce positions, close them, or flip from long to short.

An important safety feature: **reducing trades always go through**. If you have an open long position and want to sell to close it, the system bypasses all risk checks (cooldown, throttle, leverage, margin, daily loss). You can always exit a position.

**Live Mode**
Routes to actual exchange executors (Hyperliquid REST, Drift RPC, Jupiter swap). Requires API keys. Enforces a 300-second cooldown between trades, stricter integrity checks, and execution agent pre-trade validation.

**Fail-Open Execution**
If a live executor fails, the system falls back to paper mode automatically and logs the failure. Trading never silently fails — you always get a response.

### Stage 5: Monitor (The Dashboard)

A single-page web application with 8 tabs, built with vanilla HTML/CSS/JavaScript and Chart.js. No React, no framework — fast, simple, and maintainable.

**Index Tab**
The main overview. Shows the Tariff Pressure Index value, shock score, rate of change, and a dual-axis chart of index history. Below that: macro prediction (probability of BTC up, confidence, drivers) and the Macro Terminal showing WITS tariff series, rolling delta, country weights, and correlation heatmap.

**Markets Tab**
Multi-venue price table showing SOL, BTC, ETH prices from all sources with confidence scores. Funding rate chart. Carry scores. Market microstructure (orderbook imbalance, basis, spread). Solana execution quality. Funding arbitrage signals. Basis monitor. A collapsible data feed status panel showing the health of all 7 data sources.

**Divergence Tab**
Cross-venue spread chart and table. Shows which assets have price gaps between exchanges, the spread in basis points, and dislocation alerts.

**Stablecoins Tab**
USDC, USDT, DAI peg status cards. Depeg heatmap. Stress indicators. Peg-break probability. Flow momentum (risk-on/off indicator).

**Strategy Tab**
Shows which of the 5 trading rules are currently triggered. Adaptive risk weights (how the system is adjusting strategy based on market regime). Portfolio proposal with allocation bars and reasoning.

**Execution Tab**
Decision Data Status panel (shows data quality before you trade). Order submission form. Open positions table (with side: long/short). PnL attribution. Execution Quality Index. Paper trade history.

**Risk Tab**
Stress test scenarios (run them on demand). Risk guardrails status. Monte Carlo VaR/CVaR calculator. Regime analysis. Liquidation heatmap (color-coded probability grid).

**Agents Tab**
All 7 agent signals displayed as cards with confidence badges (color-coded percentage), severity indicators, direction arrows, proposed actions, expandable reasoning sections, and data timestamps. Agent registry showing all agents with their status and descriptions.

**Event Timeline (Always Visible)**
At the bottom of every tab: a color-coded feed of the last 50 system events. Green for fills, red for errors, yellow for alerts, blue for informational, purple for agent signals. Shows what the system is doing in real time.

---

## Real-Time Architecture

The system uses two communication channels:

**WebSocket (Primary)**
The frontend connects to `/ws/live` and receives events in real time as they happen — order fills, risk alerts, agent signals, index updates. The connection auto-reconnects with exponential backoff if it drops. When the browser tab is hidden, reconnection is deferred to save resources.

**REST Polling (Backup)**
Every 5 seconds, the frontend polls the active tab's data endpoints. This ensures data stays current even if the WebSocket connection drops temporarily. Polling pauses when the browser tab is hidden or when auto-refresh is toggled off.

**Event Bus**
All components communicate through a unified event bus with 61 event types. Events are published to Redis pub/sub (for real-time WebSocket broadcast) and persisted to PostgreSQL (for the event timeline and history). This means nothing is lost — every order, alert, signal, and error is recorded.

---

## Safety Design

The system is built around three safety principles:

**1. Fail-Open**
If any external API is unreachable, returns errors, or requires credentials that aren't configured, the affected feature degrades gracefully. The rest of the system continues working. No single point of failure can crash the desk.

**2. Paper Mode Default**
The system ships in paper mode. No real money can be spent unless someone explicitly sets `EXECUTION_MODE=live` and provides exchange API keys. Paper trades are tracked identically to live trades, so you can validate strategies without risk.

**3. You Can Always Exit**
Position-reducing trades (selling a long, buying to close a short) bypass all risk constraints. Cooldown timers, leverage limits, margin checks, daily loss limits, and throttle flags — none of them can prevent you from closing a position. This ensures you're never trapped in a position by the system's own safety mechanisms.

---

## Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Python + FastAPI | Fast async API framework, great for WebSocket support |
| Database | PostgreSQL | Reliable persistence for events, positions, and market data |
| Cache/PubSub | Redis | Fast in-memory cache for state snapshots + pub/sub for real-time events |
| Frontend | Vanilla JS + Chart.js | No framework overhead, fast renders, simple to maintain |
| Server | Uvicorn | ASGI server for async Python |
| Scheduling | APScheduler | Reliable periodic job execution for data ingestion |
| Testing | pytest | 98 tests across 6 files |

---


## Data Flow Diagram

```
     World Bank WITS ──┐
     GDELT News ───────┤
     Pyth Oracle ──────┤
     Kraken Exchange ──┼──→ Ingest Layer (6 scheduled jobs, all fail-open)
     CoinGecko ────────┤              │
     Drift Protocol ───┤              ▼
     Hyperliquid WS ───┘     Redis State Store (snapshots with TTLs)
                                      │
                         ┌────────────┼────────────┐
                         ▼            ▼            ▼
                   Compute Layer  Event Bus    WebSocket
                   (27 modules)   (Redis +     Server
                         │        Postgres)       │
                         ▼            │           ▼
                    API Routes        │      Frontend
                    (26 endpoints)    │      (real-time
                         │           │       updates)
                         ▼           │
                    Agent Layer      │
                    (7 agents)       │
                         │           │
                         ▼           │
                    Execution    ◄───┘
                    Router
                    (risk check →
                     price check →
                     paper/live fill)
                         │
                         ▼
                    PostgreSQL
                    (events, positions,
                     market data, orders)
```

---

## Configuration

All configuration is done through environment variables with safe defaults:

| Variable | Default | What it controls |
|----------|---------|-----------------|
| `EXECUTION_MODE` | `paper` | Paper (simulated) or live (real money) trading |
| `PRICE_FRESHNESS_THRESHOLD_S` | `30` | Maximum age of price data before trades are blocked/degraded |
| `PRICE_INTEGRITY_BLOCK_LIVE` | `true` | Whether price integrity WARNING blocks live trades |
| `MAX_LEVERAGE` | `3.0` | Maximum allowed leverage multiplier |
| `MAX_MARGIN_USAGE` | `0.6` | Maximum fraction of equity used as margin |
| `MAX_DAILY_LOSS` | `500` | Maximum daily loss in USD before trading is blocked |
| `COOLDOWN_SECONDS` | `300` | Seconds between trades (live mode only) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `ADAPTIVE_WEIGHTS` | `1` | Enable/disable adaptive risk weighting |
| `HYPERLIQUID_API_KEY` | _(empty)_ | Required for live Hyperliquid trading |
| `SOLANA_PRIVATE_KEY` | _(empty)_ | Required for live Drift/Jupiter trading |
| `SOLANA_RPC_URL` | _(empty)_ | Solana RPC endpoint for live execution |

---

## How to Use It

1. **Start the app**: `python main.py` — launches on port 5000
2. **Open the dashboard**: Navigate to the root URL
3. **Monitor**: Watch the Index tab for tariff pressure, Markets tab for prices, Agents tab for AI signals
4. **Paper trade**: Go to the Execution tab, fill in the order form (venue: paper, market: SOL-PERP, side: buy/sell, size, optional price), and submit
5. **Analyze risk**: Use the Risk tab to run stress tests, Monte Carlo simulations, and view the liquidation heatmap
6. **Check data quality**: The Decision Data Status panel in the Execution tab shows whether price data is fresh and reliable before you trade

The system runs continuously, collecting data, analyzing markets, and producing signals — whether or not anyone is watching. When you open the dashboard, you see the current state instantly via WebSocket and REST polling.

---

## Testing

98 automated tests verify the system's core logic:

- **Tariff Index calculation** — Weighted composition, edge cases, boundary values
- **Shock score computation** — Z-score math, spike detection, empty data handling
- **Divergence detection** — Spread calculations, alert triggering, multi-venue scenarios
- **Risk engine constraints** — Leverage limits, margin caps, daily loss limits, cooldown behavior, position-reducing bypass
- **Paper trading** — BUY creates long, SELL creates short, reduce/close/flip positions, event emission, side field correctness
- **Phase 3 features** — Basis engine, funding arb, stable flow, adaptive weights, portfolio optimizer, liquidation heatmap, execution metrics, Solana liquidity

All tests are unit tests that run without external dependencies (no API calls, no database, no Redis). They complete in under 3 seconds.
