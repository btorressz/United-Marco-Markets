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
