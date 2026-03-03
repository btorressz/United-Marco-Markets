# United Marco Markets (Tariff Risk Desk) — Full Project Explanation

## What Is This?

The Tariff Risk Desk is a real-time trading intelligence platform that connects two worlds that don't usually talk to each other: **global trade policy** (tariffs, sanctions, trade wars) and **cryptocurrency markets** (Bitcoin, Solana, Ethereum, stablecoins). The core idea is that when governments impose tariffs or trade tensions escalate, it creates ripple effects across financial markets — including crypto. This system detects those signals early and helps traders respond.

Think of it as a command center that watches the news, monitors prices across multiple exchanges, runs risk calculations, and tells you what's happening — all in one dashboard.

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

