CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    source VARCHAR(200) NOT NULL,
    payload JSONB DEFAULT '{}',
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS index_history (
    id SERIAL PRIMARY KEY,
    index_level FLOAT NOT NULL,
    rate_of_change FLOAT NOT NULL DEFAULT 0.0,
    shock_score FLOAT NOT NULL DEFAULT 0.0,
    components JSONB DEFAULT '{}',
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS market_ticks (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    venue VARCHAR(50) NOT NULL,
    price FLOAT NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 1.0,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS funding_ticks (
    id SERIAL PRIMARY KEY,
    venue VARCHAR(50) NOT NULL,
    market VARCHAR(50) NOT NULL,
    funding_rate FLOAT NOT NULL,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    venue VARCHAR(50) NOT NULL,
    market VARCHAR(50) NOT NULL,
    size FLOAT NOT NULL,
    entry_price FLOAT NOT NULL,
    pnl FLOAT NOT NULL DEFAULT 0.0,
    margin FLOAT NOT NULL DEFAULT 0.0,
    liq_price FLOAT,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS paper_trades (
    id SERIAL PRIMARY KEY,
    venue VARCHAR(50) NOT NULL,
    market VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    size FLOAT NOT NULL,
    price FLOAT NOT NULL,
    order_type VARCHAR(20) NOT NULL DEFAULT 'limit',
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_ts ON events (ts DESC);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events (event_type);
CREATE INDEX IF NOT EXISTS idx_index_history_ts ON index_history (ts DESC);
CREATE INDEX IF NOT EXISTS idx_market_ticks_ts ON market_ticks (ts DESC);
CREATE INDEX IF NOT EXISTS idx_market_ticks_venue ON market_ticks (venue);
CREATE INDEX IF NOT EXISTS idx_funding_ticks_ts ON funding_ticks (ts DESC);
CREATE INDEX IF NOT EXISTS idx_positions_ts ON positions (ts DESC);
CREATE INDEX IF NOT EXISTS idx_paper_trades_ts ON paper_trades (ts DESC);

CREATE TABLE IF NOT EXISTS regime_snapshots (
    id SERIAL PRIMARY KEY,
    shock_state VARCHAR(50) NOT NULL,
    funding_regime VARCHAR(50) NOT NULL,
    vol_regime VARCHAR(50) NOT NULL,
    tariff_index FLOAT NOT NULL DEFAULT 0.0,
    price FLOAT NOT NULL DEFAULT 0.0,
    return_4h FLOAT,
    return_24h FLOAT,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_regime_snapshots_ts ON regime_snapshots (ts DESC);

CREATE TABLE IF NOT EXISTS stablecoin_ticks (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    price FLOAT NOT NULL,
    depeg_bps FLOAT NOT NULL DEFAULT 0.0,
    source VARCHAR(50) NOT NULL DEFAULT 'unknown',
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stablecoin_ticks_ts ON stablecoin_ticks (ts DESC);
