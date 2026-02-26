const API = (() => {
  const BASE = '';

  async function fetchJSON(path) {
    try {
      const res = await fetch(BASE + path);
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`API ${res.status}: ${detail}`);
      }
      return await res.json();
    } catch (err) {
      console.error(`[API] Error fetching ${path}:`, err);
      throw err;
    }
  }

  async function postJSON(path, body) {
    try {
      const res = await fetch(BASE + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        let msg = `API ${res.status}`;
        try {
          const data = await res.json();
          const detail = data.detail || data;
          if (detail && detail.reasons) {
            msg = detail.reasons.join('; ');
          } else if (detail && detail.message) {
            msg = detail.message;
          } else if (typeof detail === 'string') {
            msg = detail;
          }
        } catch (_) {
          msg = await res.text().catch(() => msg);
        }
        throw new Error(msg);
      }
      return await res.json();
    } catch (err) {
      if (err.message && !err.message.startsWith('[API]')) {
        console.warn(`[API] ${path}: ${err.message}`);
      }
      throw err;
    }
  }

  return {
    getIndexLatest: () => fetchJSON('/api/index/latest'),
    getIndexHistory: (window = '7d') => fetchJSON(`/api/index/history?window=${window}`),
    getIndexComponents: () => fetchJSON('/api/index/components'),

    getMarketLatest: () => fetchJSON('/api/markets/latest'),
    getMarketHistory: (venue = 'hyperliquid', window = '1h') =>
      fetchJSON(`/api/markets/history?venue=${venue}&window=${window}`),
    getFunding: () => fetchJSON('/api/markets/funding'),
    getIntegrity: () => fetchJSON('/api/markets/integrity'),

    getDivergenceSpreads: () => fetchJSON('/api/divergence/spreads'),
    getDivergenceAlerts: () => fetchJSON('/api/divergence/alerts'),

    getStablecoinHealth: () => fetchJSON('/api/stablecoins/health'),
    getStablecoinAlerts: () => fetchJSON('/api/stablecoins/alerts'),

    getPrediction: () => fetchJSON('/api/predict/latest'),

    postMonteCarlo: (params) => postJSON('/api/montecarlo/run', params),

    getCarry: () => fetchJSON('/api/yield/carry'),

    getMicrostructure: () => fetchJSON('/api/microstructure/snapshot'),

    getAgentSignals: () => fetchJSON('/api/agents/signals'),
    getAgentRegistry: () => fetchJSON('/api/agents/status'),

    getRulesEvaluation: () => fetchJSON('/api/rules/evaluate'),
    getRulesStatus: () => fetchJSON('/api/rules/status'),

    getPositions: () => fetchJSON('/api/execution/positions'),
    getPaperTrades: () => fetchJSON('/api/execution/paper-trades'),
    postOrder: (order) => postJSON('/api/execution/order', order),

    getRiskStatus: () => fetchJSON('/api/risk/status'),
    postStressTest: (scenario) => postJSON('/api/risk/stress-test', scenario),
    getGuardrails: () => fetchJSON('/api/risk/guardrails'),

    getEvents: (limit = 50) => fetchJSON(`/api/events/?limit=${limit}`),
    getHealth: () => fetchJSON('/api/health/'),

    getEQI: () => fetchJSON('/api/metrics/eqi'),
    getSolanaQuality: () => fetchJSON('/api/solana/quality'),
    getSolanaCongestion: () => fetchJSON('/api/solana/congestion'),
    getFundingArb: () => fetchJSON('/api/funding-arb/latest'),
    getBasisLatest: () => fetchJSON('/api/basis/latest'),
    getBasisFeasibility: () => fetchJSON('/api/basis/feasibility'),
    getStableFlow: () => fetchJSON('/api/stable-flow/latest'),
    getAdaptiveWeights: () => fetchJSON('/api/rules/adaptive-weights'),
    getPortfolioProposal: (method = 'risk_parity') => fetchJSON(`/api/portfolio/proposal?method=${method}`),
    getLiquidationHeatmap: () => fetchJSON('/api/liquidation/heatmap'),
    getRegimeAnalogs: () => fetchJSON('/api/risk/regime-analogs'),
    getMacroTerminal: () => fetchJSON('/api/index/macro-terminal'),
    getFeedStatus: () => fetchJSON('/api/health/feeds'),
  };
})();
