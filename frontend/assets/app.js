const App = (() => {
  let activeTab = 'index';
  let refreshInterval = null;
  let initialized = false;
  let autoRefresh = true;
  let tabVisible = true;
  let wsMessageBuffer = [];
  let wsFlushTimer = null;
  let currentTheme = 'dark';
  const chartTimeframes = { index: '7d' };

  function init() {
    if (initialized) return;
    initialized = true;

    initTheme();
    initTabs();
    initCharts();
    initWebSocket();
    initOrderForm();
    initStressTestForm();
    initMCForm();
    initFeedStatusToggle();
    initAutoRefreshToggle();
    initTimeframeSelectors();
    initVisibilityListener();

    refresh();
    refreshInterval = setInterval(refresh, 5000);

    console.log('[App] Tariff Risk Desk initialized');
  }

  function initTheme() {
    const saved = localStorage.getItem('theme') || 'dark';
    applyTheme(saved);
    const btn = document.getElementById('theme-toggle');
    if (btn) {
      btn.addEventListener('click', () => {
        const next = currentTheme === 'dark' ? 'light' : 'dark';
        applyTheme(next);
        localStorage.setItem('theme', next);
      });
    }
  }

  function applyTheme(theme) {
    currentTheme = theme;
    if (theme === 'light') {
      document.documentElement.setAttribute('data-theme', 'light');
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
    const moonIcon = document.getElementById('theme-icon-moon');
    const sunIcon = document.getElementById('theme-icon-sun');
    const label = document.getElementById('theme-label');
    if (moonIcon) moonIcon.style.display = theme === 'dark' ? 'inline-block' : 'none';
    if (sunIcon) sunIcon.style.display = theme === 'light' ? 'inline-block' : 'none';
    if (label) label.textContent = theme === 'dark' ? 'DARK' : 'LIGHT';
    if (typeof Charts !== 'undefined' && Charts.reThemeAllCharts) {
      setTimeout(() => Charts.reThemeAllCharts(), 50);
    }
  }

  function initAutoRefreshToggle() {
    const btn = document.getElementById('auto-refresh-toggle');
    if (!btn) return;
    btn.addEventListener('click', () => {
      autoRefresh = !autoRefresh;
      btn.className = 'auto-refresh-toggle' + (autoRefresh ? ' on' : '');
      btn.innerHTML = `<span class="refresh-dot"></span> ${autoRefresh ? 'AUTO' : 'PAUSED'}`;
      if (autoRefresh) {
        refresh();
      }
    });
  }

  function initTimeframeSelectors() {
    document.querySelectorAll('.timeframe-selector').forEach(container => {
      const chartName = container.dataset.chart;
      container.querySelectorAll('.tf-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          container.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          chartTimeframes[chartName] = btn.dataset.tf;
          refreshActiveTab();
        });
      });
    });
  }

  function initVisibilityListener() {
    document.addEventListener('visibilitychange', () => {
      tabVisible = !document.hidden;
      if (tabVisible && autoRefresh) {
        refresh();
      }
    });
  }

  function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        if (tab) switchTab(tab);
      });
    });
  }

  function switchTab(tab) {
    activeTab = tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + tab));
    refreshActiveTab();
  }

  function initCharts() {
    window._indexChart = Charts.createIndexChart('index-chart');
    window._fundingChart = Charts.createFundingChart('funding-chart');
    window._divergenceChart = Charts.createDivergenceChart('divergence-chart');
    window._mcChart = Charts.createMCChart('mc-chart');
  }

  function initWebSocket() {
    WS.on('connectionChange', (connected) => {
      UI.updateConnectionStatus(connected);
    });

    WS.on('message', (data) => {
      if (data.type === 'snapshot') {
        UI.addEventToTimeline({ event_type: 'CONNECTED', source: 'ws', ts: data.ts, payload: { message: data.message } }, true);
      } else if (data.type === 'pong') {
        return;
      } else {
        wsMessageBuffer.push(data);
        if (!wsFlushTimer) {
          wsFlushTimer = setTimeout(flushWsMessages, 200);
        }
      }
    });

    WS.connect();
  }

  function flushWsMessages() {
    wsFlushTimer = null;
    const batch = wsMessageBuffer.splice(0);
    batch.forEach(msg => UI.addEventToTimeline(msg, true));
  }

  function initOrderForm() {
    const form = document.getElementById('order-form');
    if (!form) return;
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = form.querySelector('button[type="submit"]');
      btn.disabled = true;
      btn.textContent = 'Submitting...';

      try {
        const order = {
          venue: form.venue.value,
          market: form.market.value,
          side: form.side.value,
          size: parseFloat(form.size.value),
          price: form.price.value ? parseFloat(form.price.value) : null,
        };
        const result = await API.postOrder(order);
        UI.addEventToTimeline({ event_type: 'ORDER_SUBMITTED', source: 'user', ts: new Date().toISOString(), payload: { message: `${order.side} ${order.size} ${order.market} on ${order.venue}` } }, true);
        form.reset();
        refreshActiveTab();
      } catch (err) {
        UI.addEventToTimeline({ event_type: 'ERROR', source: 'user', ts: new Date().toISOString(), payload: { message: 'Order failed: ' + err.message } }, true);
      } finally {
        btn.disabled = false;
        btn.textContent = 'Submit Order';
      }
    });
  }

  function initStressTestForm() {
    const form = document.getElementById('stress-form');
    if (!form) return;
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = form.querySelector('button[type="submit"]');
      btn.disabled = true;
      btn.textContent = 'Running...';

      try {
        const scenario = form.scenario.value;
        const result = await API.postStressTest({ scenario });
        UI.renderRiskTab({ stressResult: result });
      } catch (err) {
        UI.addEventToTimeline({ event_type: 'ERROR', source: 'stress_test', ts: new Date().toISOString(), payload: { message: 'Stress test failed: ' + err.message } }, true);
      } finally {
        btn.disabled = false;
        btn.textContent = 'Run Test';
      }
    });
  }

  function convertHorizonToHours(value, unit) {
    switch (unit) {
      case 'minutes': return Math.max(0.02, Math.round(value / 60 * 100) / 100);
      case 'days': return Math.min(48, value * 24);
      default: return value;
    }
  }

  function formatHorizonSummary(value, unit) {
    const label = value === 1 ? unit.replace(/s$/, '') : unit;
    return `Horizon: ${value} ${label}`;
  }

  function initMCForm() {
    const form = document.getElementById('mc-form');
    if (!form) return;
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = form.querySelector('button[type="submit"]');
      btn.disabled = true;
      btn.textContent = 'Running...';

      try {
        const horizonValue = parseFloat(form.horizon_value.value);
        const horizonUnit = form.horizon_unit.value;
        const horizonHours = convertHorizonToHours(horizonValue, horizonUnit);

        const summaryEl = document.getElementById('mc-horizon-summary');
        if (summaryEl) {
          summaryEl.textContent = formatHorizonSummary(horizonValue, horizonUnit);
          summaryEl.style.display = 'block';
        }

        const params = {
          symbol: form.symbol.value,
          position_size: parseFloat(form.position_size.value),
          horizon_hours: horizonHours,
          n_paths: parseInt(form.n_paths.value),
        };
        const result = await API.postMonteCarlo(params);
        UI.renderRiskTab({ mcResult: result });
      } catch (err) {
        UI.addEventToTimeline({ event_type: 'ERROR', source: 'monte_carlo', ts: new Date().toISOString(), payload: { message: 'MC simulation failed: ' + err.message } }, true);
      } finally {
        btn.disabled = false;
        btn.textContent = 'Run MC';
      }
    });
  }

  function initFeedStatusToggle() {
    const btn = document.getElementById('feed-status-toggle');
    const panel = document.getElementById('feed-status-panel');
    if (btn && panel) {
      btn.addEventListener('click', () => {
        const hidden = panel.style.display === 'none';
        panel.style.display = hidden ? 'block' : 'none';
        btn.textContent = hidden ? 'Hide' : 'Show';
      });
    }
  }

  async function refresh() {
    if (!autoRefresh || !tabVisible) return;
    refreshHealth();
    refreshTimeline();
    refreshActiveTab();
  }

  async function refreshActiveTab() {
    try {
      switch (activeTab) {
        case 'index': await refreshIndex(); break;
        case 'markets': await refreshMarkets(); break;
        case 'divergence': await refreshDivergence(); break;
        case 'stablecoins': await refreshStablecoins(); break;
        case 'strategy': await refreshStrategy(); break;
        case 'execution': await refreshExecution(); break;
        case 'risk': await refreshRisk(); break;
        case 'agents': await refreshAgents(); break;
      }
    } catch (err) {
      console.error(`[App] Error refreshing ${activeTab}:`, err);
    }
  }

  async function refreshIndex() {
    const tf = chartTimeframes.index || '7d';
    const [latest, history, components, prediction, macroTerminal] = await Promise.allSettled([
      API.getIndexLatest(),
      API.getIndexHistory(tf),
      API.getIndexComponents(),
      API.getPrediction(),
      API.getMacroTerminal(),
    ]);
    UI.renderIndexTab({
      latest: latest.status === 'fulfilled' ? latest.value : null,
      history: history.status === 'fulfilled' ? history.value : null,
      components: components.status === 'fulfilled' ? components.value : null,
      prediction: prediction.status === 'fulfilled' ? prediction.value : null,
      macroTerminal: macroTerminal.status === 'fulfilled' ? macroTerminal.value : null,
    });
  }

  async function refreshMarkets() {
    const [latest, funding, carry, microstructure, integrity, solanaQuality, fundingArb, basis, feedStatus] = await Promise.allSettled([
      API.getMarketLatest(),
      API.getFunding(),
      API.getCarry(),
      API.getMicrostructure(),
      API.getIntegrity(),
      API.getSolanaQuality(),
      API.getFundingArb(),
      API.getBasisLatest(),
      API.getFeedStatus(),
    ]);
    UI.renderMarketsTab({
      latest: latest.status === 'fulfilled' ? latest.value : null,
      funding: funding.status === 'fulfilled' ? funding.value : null,
      carry: carry.status === 'fulfilled' ? carry.value : null,
      microstructure: microstructure.status === 'fulfilled' ? microstructure.value : null,
      integrity: integrity.status === 'fulfilled' ? integrity.value : null,
      solanaQuality: solanaQuality.status === 'fulfilled' ? solanaQuality.value : null,
      fundingArb: fundingArb.status === 'fulfilled' ? fundingArb.value : null,
      basis: basis.status === 'fulfilled' ? basis.value : null,
    });
    if (feedStatus.status === 'fulfilled') {
      UI.renderFeedStatus(feedStatus.value);
    }
  }

  async function refreshDivergence() {
    const [spreads, alerts] = await Promise.allSettled([
      API.getDivergenceSpreads(),
      API.getDivergenceAlerts(),
    ]);
    UI.renderDivergenceTab({
      spreads: spreads.status === 'fulfilled' ? spreads.value : null,
      alerts: alerts.status === 'fulfilled' ? alerts.value : null,
    });
  }

  async function refreshStablecoins() {
    const [health, alerts, stableFlow] = await Promise.allSettled([
      API.getStablecoinHealth(),
      API.getStablecoinAlerts(),
      API.getStableFlow(),
    ]);
    UI.renderStablecoinsTab({
      health: health.status === 'fulfilled' ? health.value : null,
      alerts: alerts.status === 'fulfilled' ? alerts.value : null,
      stableFlow: stableFlow.status === 'fulfilled' ? stableFlow.value : null,
    });
  }

  async function refreshStrategy() {
    const [evaluation, status, adaptiveWeights, portfolio] = await Promise.allSettled([
      API.getRulesEvaluation(),
      API.getRulesStatus(),
      API.getAdaptiveWeights(),
      API.getPortfolioProposal(),
    ]);
    UI.renderStrategyTab({
      evaluation: evaluation.status === 'fulfilled' ? evaluation.value : null,
      status: status.status === 'fulfilled' ? status.value : null,
      adaptiveWeights: adaptiveWeights.status === 'fulfilled' ? adaptiveWeights.value : null,
      portfolio: portfolio.status === 'fulfilled' ? portfolio.value : null,
    });
  }

  async function refreshExecution() {
    const [positions, trades, eqi, integrity, health, indexData] = await Promise.allSettled([
      API.getPositions(),
      API.getPaperTrades(),
      API.getEQI(),
      API.getIntegrity(),
      API.getHealth(),
      API.getIndexLatest(),
    ]);
    UI.renderDecisionDataPanel({
      integrity: integrity.status === 'fulfilled' ? integrity.value : null,
      health: health.status === 'fulfilled' ? health.value : null,
      indexData: indexData.status === 'fulfilled' ? indexData.value : null,
    });
    UI.renderExecutionTab({
      positions: positions.status === 'fulfilled' ? positions.value : null,
      trades: trades.status === 'fulfilled' ? trades.value : null,
      eqi: eqi.status === 'fulfilled' ? eqi.value : null,
    });
  }

  async function refreshRisk() {
    const [status, guardrails, heatmap, analogs] = await Promise.allSettled([
      API.getRiskStatus(),
      API.getGuardrails(),
      API.getLiquidationHeatmap(),
      API.getRegimeAnalogs(),
    ]);
    UI.renderRiskTab({
      status: status.status === 'fulfilled' ? status.value : null,
      guardrails: guardrails.status === 'fulfilled' ? guardrails.value : null,
      heatmap: heatmap.status === 'fulfilled' ? heatmap.value : null,
      analogs: analogs.status === 'fulfilled' ? analogs.value : null,
    });
  }

  async function refreshAgents() {
    const [signals, registry] = await Promise.allSettled([
      API.getAgentSignals(),
      API.getAgentRegistry(),
    ]);
    UI.renderAgentsTab({
      signals: signals.status === 'fulfilled' ? signals.value : null,
      registry: registry.status === 'fulfilled' ? registry.value : null,
    });
  }

  async function refreshHealth() {
    try {
      const health = await API.getHealth();
      const el = document.getElementById('health-info');
      if (el) {
        const dbIcon = health.database ? '\u25CF' : '\u25CB';
        const dbColor = health.database ? 'var(--accent-green)' : 'var(--accent-red)';
        el.innerHTML = `<span style="color:${dbColor}">${dbIcon}</span> DB &nbsp; <span style="color:var(--text-muted)">v${health.version || '0.1.0'}</span>`;
      }
    } catch {}
  }

  async function refreshTimeline() {
    try {
      const events = await API.getEvents(50);
      UI.renderTimeline(events);
    } catch {}
  }

  return { init, switchTab };
})();

document.addEventListener('DOMContentLoaded', App.init);
