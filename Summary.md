# Tariff Risk Desk — Full Summary

## What Is This?

The Tariff Risk Desk is a real-time trading intelligence dashboard that watches global trade policy (tariffs, geopolitical news) and connects it to cryptocurrency markets. It helps a trader understand how macro events like tariff announcements or political tensions might affect crypto prices, and gives them tools to manage risk, spot opportunities, and execute trades safely.

Think of it as a command center that sits between "what's happening in the world" and "what should I do with my portfolio."

---

## How It Works, Step by Step

### 1. Data Collection (The Inputs)

The system constantly pulls data from multiple sources, running on automatic timers:

- **World Bank WITS**: Real tariff rate data between countries. This is the core macro signal — when tariffs go up between major trading partners, markets tend to react.
- **GDELT**: A global news monitoring system. The app reads news tone and volume to detect "shock events" — sudden spikes in negative geopolitical coverage.
- **Pyth Network**: A blockchain-based price oracle. This is the primary, most trusted source for crypto prices (SOL, BTC, ETH).
- **Kraken**: A major crypto exchange. Used as a secondary price source.
- **CoinGecko**: A crypto data aggregator. Used as a fallback if the other two price sources are unavailable.
- **Hyperliquid**: A decentralized perpetual futures exchange. The app pulls orderbook data, funding rates, and market microstructure from here.
- **Drift Protocol**: Another decentralized perp exchange on Solana. Used for cross-venue comparison and funding rate arbitrage detection.

If any of these sources go down or return errors, the system keeps running — it never crashes due to a missing data feed. This is called "fail-open" design.

### 2. The Tariff Pressure Index (The Core Signal)

The app computes a single number from 0 to 100 called the Tariff Pressure Index. This combines:

- Current tariff rates from WITS data
- News shock scores from GDELT
- Rate of change (is pressure increasing or decreasing?)
- Country-specific weights (tariffs involving larger trading partners matter more)

When this index spikes, it means trade policy tension is rising, which historically correlates with crypto market volatility. The dashboard shows this index on a chart with selectable timeframes (1 hour, 4 hours, 1 day, 7 days).

### 3. Market Monitoring (What Are Prices Doing?)

The Markets tab shows:

- **Live prices** from all connected venues, with the source and confidence level
- **Funding rates** — the periodic payments between long and short traders on perpetual futures. These indicate market sentiment.
- **Carry scores** — how much you'd earn (or pay) annually just by holding a position, based on funding rates
- **Microstructure** — orderbook imbalance (are there more buyers or sellers?), bid-ask spread, and market depth
- **Price integrity checks** — the system cross-checks prices across venues. If Pyth says SOL is $150 but Kraken says $145, something is wrong and the system flags it.
- **Solana execution quality** — RPC latency, congestion detection, and route analysis for Solana-based trades
- **Feed status** — a collapsible panel showing every data source, whether it's healthy, how old its data is, and which source is currently authoritative

### 4. Divergence Detection (Spotting Mismatches)

The Divergence tab monitors price differences between venues. If SOL is trading at $150.00 on Hyperliquid but $149.50 on Drift, that's a 50-cent spread. The system:

- Tracks these spreads in real-time
- Alerts when spreads exceed normal thresholds
- Flags "dislocations" — large, sudden price gaps that might indicate a trading opportunity or a broken feed

### 5. Stablecoin Monitoring (Is the Dollar Peg Holding?)

Stablecoins (USDC, USDT, DAI) are supposed to be worth exactly $1.00. The Stablecoins tab watches:

- **Peg status** — current price and deviation in basis points (1 bp = 0.01%)
- **Depeg heatmap** — a visual showing which stablecoins are closest to breaking their peg
- **Stress and peg-break probability** — estimated likelihood of a stablecoin losing its peg based on current conditions
- **Flow momentum** — tracking whether money is flowing into or out of stablecoins (a "risk-off" signal when money flows in, "risk-on" when it flows out)
- **Stablecoin playbook** — automated response recommendations if a depeg event occurs (e.g., "rotate from USDT to USDC if USDT depeg exceeds 50 bps")

### 6. Strategy Engine (What Should I Do?)

The Strategy tab runs five configurable trading rules that evaluate current conditions and propose actions:

- **Tariff shock rule** — if the tariff index spikes, suggest opening a short or reducing exposure
- **Funding rate rule** — if funding is extremely positive, suggest shorting (the market is overleveraged long)
- **Divergence rule** — if venue prices diverge significantly, suggest an arbitrage trade
- **Volatility regime rule** — adjust position sizing based on whether we're in a low-vol or high-vol environment
- **Stable rotation rule** — if stablecoin health deteriorates, suggest rotating into safer stables

Each rule produces a specific action: open long, open short, reduce position, or rotate to stablecoins. The system also shows:

- **Adaptive risk weights** — the relative importance of each signal adjusts automatically based on the current market regime
- **Portfolio proposals** — suggested allocations across assets using methods like risk parity, mean-variance optimization, or Kelly criterion. These are proposals only — the system never auto-trades.

### 7. Strategy Sandbox

A comparison tool that lets you test two different strategy configurations against the same market conditions side by side. You can tweak rule thresholds, risk limits, or allocation methods and see how the outputs differ without risking real money.

### 8. Replay Engine

Takes historical events from the event log and replays them through the strategy engine. This lets you ask "what would my strategy have done during last week's tariff shock?" and see the simulated trades and outcomes.

### 9. Execution (Placing Trades)

The Execution tab is where trades actually happen. It includes:

- **Decision Data Status panel** — before you trade, this shows whether your data is fresh and reliable. It checks: Is the tariff index recent? Are prices current? Is price integrity OK? If data is stale or degraded, it warns you.
- **Paper trading** — by default, all trades are simulated. You can submit orders (buy/sell, any venue, any market, any size) and they execute in a virtual environment with position tracking and fill simulation.
- **Live execution** (optional) — if you set EXECUTION_MODE=live and provide API keys, the system can route real orders to Hyperliquid, Drift, or Jupiter (Solana swap aggregator). This is disabled by default for safety.
- **Position tracking** — shows all open positions with venue, market, side, size, entry price, and timestamp
- **PnL attribution** — breaks down profit and loss by position
- **Execution Quality Index (EQI)** — a score from 0-100 measuring how well trades are being executed, including latency percentiles (p50, p95), average slippage in basis points, and fill counts

### 10. Slippage Model

Estimates how much slippage (price movement against you) to expect for a given order size on each venue. It considers orderbook depth, spread, volatility, and recent slippage history to compute maximum safe order sizes — the largest trade you can make without excessive slippage.

### 11. Risk Management (How Exposed Am I?)

The Risk tab provides:

- **Throttle system** — if risk limits are breached (too much leverage, too much margin used, too large daily loss), the system activates a throttle that blocks new trades until conditions normalize
- **Guardrails** — configurable limits for max leverage, max margin usage, max daily loss, and cooldown periods
- **Stress tests** — run four predefined scenarios (tariff shock, liquidity crisis, flash crash, funding flip) against your current positions to see estimated P&L impact, max drawdown, and whether you'd face a margin call
- **Monte Carlo simulation** — runs thousands of random price paths (up to 10,000) to estimate Value at Risk (VaR) and Conditional Value at Risk (CVaR) at the 95% confidence level. You can set the time horizon in minutes, hours, or days. Results include a distribution chart.
- **Regime replay** — looks at past market regimes similar to the current one and shows what returns looked like historically (average 4-hour return, 24-hour return, win rate)
- **Liquidation heatmap** — a grid showing liquidation probability for different combinations of leverage (2x to 10x) and price drops (5% to 30%). Color-coded from green (safe) to red (likely liquidation).
- **Hedge ratio analysis** — computes rolling correlations between assets and suggests optimal hedge ratios to minimize portfolio risk

### 12. AI Agents (Automated Analysts)

Seven heuristic (rule-based, not machine learning) agents continuously evaluate market conditions and emit signals:

1. **Risk Agent** — monitors position sizing, leverage, and portfolio risk. Proposes reducing positions or blocking execution when risk is elevated.
2. **Macro Agent** — evaluates the tariff index, shock scores, and macro regime. Flags when macro conditions are deteriorating.
3. **Execution Agent** — tracks execution quality, slippage trends, and fill metrics. Warns when execution conditions are poor.
4. **Liquidity Agent** — monitors stablecoin health, depeg risk, and overall liquidity conditions. Alerts on liquidity deterioration.
5. **Hyperliquid Agent** — analyzes Hyperliquid-specific orderbook microstructure, spread width, and depth. Detects thin liquidity or unusual orderbook patterns.
6. **Jupiter Agent** — monitors Jupiter/Solana swap conditions: quote freshness, route complexity (how many hops a swap takes), price impact, slippage risk, and Solana network congestion.
7. **Hedging Agent** — position-aware agent that recommends hedge adjustments based on shock levels, volatility, funding rates, and margin usage.

Each agent signal includes:
- Severity (low/medium/high)
- Direction (bullish/bearish/neutral)
- Confidence score (0-100%)
- Proposed action (e.g., "reduce_size", "block_execution", "hedge")
- Detailed reasoning (expandable in the UI)
- Timestamps for both the signal and the data it was based on

### 13. Funding Arbitrage Detection

Compares funding rates between Hyperliquid and Drift. When one venue pays significantly more than the other, it flags an arbitrage opportunity — you could go long on the venue with negative funding (they pay you) and short on the venue with positive funding (you collect both sides).

### 14. Basis Monitor

Tracks the "basis" — the difference between perpetual futures prices and spot prices. A large positive basis means futures are trading at a premium to spot, which represents a carry trade opportunity. The system computes annualized basis in basis points and net carry (basis minus funding costs), and flags when conditions are feasible for a basis trade.

---

## The Dashboard

The frontend is a single-page application with 8 tabs:

1. **Index** — Tariff Pressure Index, Shock Score, prediction, macro terminal
2. **Markets** — Live prices, funding, carry, microstructure, Solana quality, funding arb, basis monitor, feed status
3. **Divergence** — Cross-venue spread tracking and alerts
4. **Stablecoins** — Peg monitor, depeg heatmap, stress probability, flow momentum
5. **Strategy** — Rule signals, adaptive weights, portfolio proposals
6. **Execution** — Data quality check, order form, positions, PnL, execution quality
7. **Risk** — Throttle status, guardrails, stress tests, Monte Carlo, regime replay, liquidation heatmap
8. **Agents** — All 7 agent signals with confidence badges and expandable reasoning

An always-visible **Event Timeline** at the bottom shows the last 50 events color-coded by type: green for fills, red for errors, yellow for alerts, blue for info, purple for agent signals.

### UI Features

- **Dark/Light theme** — toggle in the header, persists across browser refreshes
- **Auto-refresh** — data polls every 5 seconds, with a toggle to pause
- **WebSocket live feed** — primary updates come through a real-time WebSocket connection, with automatic reconnection and exponential backoff
- **Freshness badges** — each panel shows whether its data is LIVE (under 10 seconds old), FRESH (under 60 seconds), STALE (over 60 seconds), or DEGRADED
- **Performance optimizations** — polling pauses when the browser tab is hidden, WebSocket messages are batched every 200ms to prevent UI thrashing

---

## Technical Architecture

- **Backend**: Python with FastAPI, running on port 5000
- **Frontend**: Plain HTML, CSS, and JavaScript (no React or framework). Charts use Chart.js.
- **Database**: PostgreSQL with 8 tables for events, trades, positions, regime snapshots, and stablecoin data
- **Cache**: Redis for real-time state snapshots, throttling, and pub/sub event distribution
- **22 API route modules** serving data to the frontend
- **27 computation modules** for all analytics (index calculation, divergence detection, Monte Carlo, portfolio optimization, etc.)
- **7 AI agents** running as heuristic evaluators
- **6 data ingest jobs** running on scheduled timers (every 30 seconds to every 6 hours depending on the source)

### Safety Design

- **Paper mode by default** — no real money is at risk unless you explicitly enable live trading
- **Fail-open architecture** — missing API keys, unavailable data sources, or computation errors disable individual features but never crash the system
- **Risk guardrails** — hard limits on leverage, margin, and daily loss that block trading when breached
- **Data quality warnings** — the system tells you when data is stale before you trade on it
- **Portfolio proposals only** — the optimizer suggests allocations but never executes automatically

---

## Environment and Configuration

The app runs with a single command (`python main.py`) which starts the web server, connects to the database, launches Redis, and begins all data ingestion jobs. Configuration is through environment variables — the only required one is `DATABASE_URL` (automatically set by Replit). All others have safe defaults.

Key optional settings:
- `EXECUTION_MODE` — "paper" (default) or "live"
- `REDIS_URL` — defaults to localhost
- `HYPERLIQUID_API_KEY`, `SOLANA_PRIVATE_KEY`, `SOLANA_RPC_URL` — only needed for live execution
- `MAX_LEVERAGE`, `MAX_MARGIN_USAGE`, `MAX_DAILY_LOSS` — risk limit overrides

The system has 77 automated tests covering index calculation, shock detection, divergence alerts, risk throttling, basis engine, funding arbitrage, stable flow, adaptive weights, portfolio optimization, liquidation heatmap, execution metrics, and Solana liquidity scoring.
