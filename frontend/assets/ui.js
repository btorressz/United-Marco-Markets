const UI = (() => {
  function formatTimestamp(ts) {
    if (!ts) return '--';
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    } catch { return '--'; }
  }

  function formatNumber(n, decimals = 2) {
    if (n === null || n === undefined || isNaN(n)) return '--';
    return Number(n).toFixed(decimals);
  }

  function formatPrice(n) {
    if (n === null || n === undefined || isNaN(n)) return '--';
    return Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
  }

  function classForValue(val) {
    if (val > 0) return 'green';
    if (val < 0) return 'red';
    return '';
  }

  function renderFreshnessBadge(elementId, ts, thresholds) {
    const el = document.getElementById(elementId);
    if (!el) return;
    if (!ts) {
      el.className = 'freshness-badge nodata';
      el.innerHTML = '<span class="freshness-dot"></span> NO DATA';
      return;
    }
    const stale = (thresholds && thresholds.stale) || 120;
    const degraded = (thresholds && thresholds.degraded) || 300;
    const age = (Date.now() - new Date(ts).getTime()) / 1000;
    let level, label;
    if (age < 10) { level = 'live'; label = 'LIVE'; }
    else if (age < stale) { level = 'fresh'; label = 'FRESH'; }
    else if (age < degraded) { level = 'stale'; label = 'STALE'; }
    else { level = 'degraded'; label = 'DEGRADED'; }
    const ageText = age < 60 ? Math.round(age) + 's' : Math.round(age / 60) + 'm';
    el.className = 'freshness-badge ' + level;
    el.innerHTML = `<span class="freshness-dot"></span> ${label} <span style="opacity:0.7">${ageText} ago</span>`;
  }

  function renderDecisionDataPanel(data) {
    const panel = document.getElementById('decision-data-panel');
    if (!panel) return;
    const items = [];
    let worstLevel = 'ok';

    function addItem(label, ts, source) {
      if (!ts) {
        items.push({ label, status: 'nodata', age: '--', source: source || '--' });
        if (worstLevel !== 'degraded') worstLevel = 'degraded';
        return;
      }
      const age = (Date.now() - new Date(ts).getTime()) / 1000;
      let status = 'ok';
      if (age > 300) { status = 'degraded'; worstLevel = 'degraded'; }
      else if (age > 120) { status = 'stale'; if (worstLevel === 'ok') worstLevel = 'stale'; }
      const ageText = age < 60 ? Math.round(age) + 's' : Math.round(age / 60) + 'm';
      items.push({ label, status, age: ageText, source: source || '--' });
    }

    if (data.health) {
      addItem('System Health', data.health.ts || new Date().toISOString(), 'health');
    }
    if (data.integrity) {
      addItem('Price Integrity', data.integrity.ts, data.integrity.status || 'OK');
    }
    if (data.indexData) {
      addItem('Tariff Index', data.indexData.ts, 'index');
    }

    const panelCls = worstLevel === 'degraded' ? 'degraded' : worstLevel === 'stale' ? 'warning' : '';
    panel.className = 'decision-data-panel ' + panelCls;

    let html = '';
    if (worstLevel !== 'ok') {
      const warnMsg = worstLevel === 'degraded' ? 'Some data sources are degraded — trade with caution' : 'Some data is stale — verify before trading';
      html += `<div style="color:var(--accent-${worstLevel === 'degraded' ? 'red' : 'yellow'});font-size:12px;margin-bottom:8px;font-weight:600">&#9888; ${warnMsg}</div>`;
    }
    items.forEach(item => {
      const dotCls = item.status === 'ok' ? 'ok' : item.status === 'stale' ? 'warning' : 'error';
      html += `<div class="decision-data-row"><span><span class="feed-status-dot ${dotCls}"></span>${item.label}</span><span style="color:var(--text-muted)">${item.age} ago</span><span style="color:var(--text-muted)">${item.source}</span></div>`;
    });
    panel.innerHTML = html || '<div style="font-size:12px;color:var(--text-muted)">No data quality info available</div>';
  }

  function renderIndexTab(data) {
    const el = document.getElementById('index-value');
    const shockEl = document.getElementById('shock-value');
    const rocEl = document.getElementById('roc-value');
    const tsEl = document.getElementById('index-ts');

    if (data.latest) {
      if (el) el.textContent = formatNumber(data.latest.tariff_index, 4);
      if (shockEl) {
        shockEl.textContent = formatNumber(data.latest.shock_score, 4);
        shockEl.className = 'metric-value ' + (data.latest.shock_score > 0.5 ? 'red' : data.latest.shock_score > 0.2 ? 'yellow' : 'green');
      }
      if (tsEl) tsEl.textContent = 'Updated: ' + formatTimestamp(data.latest.ts);
      renderFreshnessBadge('index-freshness', data.latest.ts);
    }

    if (data.history && data.history.points && window._indexChart) {
      const pts = data.history.points;
      Charts.updateChart(window._indexChart, {
        labels: pts.map(p => formatTimestamp(p.ts)),
        datasets: [
          { data: pts.map(p => p.index_level) },
          { data: pts.map(p => p.shock_score) },
        ],
      });
      if (rocEl && pts.length > 0) {
        const lastRoc = pts[pts.length - 1].rate_of_change || 0;
        rocEl.textContent = formatNumber(lastRoc, 4);
        rocEl.className = 'metric-value ' + classForValue(lastRoc);
      }
    }

    if (data.components) {
      const tbody = document.getElementById('components-tbody');
      if (tbody) {
        const comps = data.components.components || {};
        tbody.innerHTML = '';
        Object.entries(comps).forEach(([name, value]) => {
          const tr = document.createElement('tr');
          tr.innerHTML = `<td>${name}</td><td>${formatNumber(value, 4)}</td>`;
          tbody.appendChild(tr);
        });
        if (data.components.wits_weight !== undefined) {
          ['wits_weight', 'gdelt_weight', 'funding_weight'].forEach(k => {
            if (data.components[k] !== undefined && !comps[k]) {
              const tr = document.createElement('tr');
              tr.innerHTML = `<td>${k}</td><td>${formatNumber(data.components[k], 4)}</td>`;
              tbody.appendChild(tr);
            }
          });
        }
      }
    }

    if (data.prediction) {
      const pred = data.prediction;
      const upEl = document.getElementById('pred-up');
      const confEl = document.getElementById('pred-confidence');
      const drvEl = document.getElementById('pred-drivers');
      if (upEl) {
        const pct = (pred.probability_up * 100).toFixed(1);
        upEl.textContent = pct + '%';
        upEl.className = 'metric-value ' + (pred.probability_up > 0.5 ? 'green' : 'red');
      }
      if (confEl) confEl.textContent = formatNumber(pred.confidence, 4);
      if (drvEl && pred.top_drivers) {
        drvEl.innerHTML = pred.top_drivers.map(d =>
          `<span class="badge badge-blue" style="margin:2px">${d[0]}: ${formatNumber(d[1], 3)}</span>`
        ).join('');
      }
    }

    if (data.macroTerminal) {
      renderMacroTerminal(data.macroTerminal);
    }
  }

  function renderMacroTerminal(mt) {
    const freshnessEl = document.getElementById('macro-terminal-freshness');
    if (freshnessEl) {
      if (mt.ts) {
        freshnessEl.textContent = 'As of: ' + formatTimestamp(mt.ts);
      } else {
        freshnessEl.textContent = '';
      }
    }

    const seriesEl = document.getElementById('macro-wits-series');
    if (seriesEl) {
      const series = mt.tariff_series || [];
      if (series.length === 0) {
        seriesEl.innerHTML = '<div class="empty-state"><div class="empty-state-text">No WITS series data available</div></div>';
      } else {
        const rows = series.slice(-20).map(s =>
          `<div class="guardrail-row"><span class="guardrail-label">${formatTimestamp(s.ts)}</span><span class="guardrail-value">${formatNumber(s.index_level, 4)}</span></div>`
        ).join('');
        seriesEl.innerHTML = `<div style="max-height:200px;overflow-y:auto">${rows}</div>`;
      }
    }

    const deltaEl = document.getElementById('macro-rolling-delta');
    if (deltaEl) {
      const deltas = mt.rolling_delta || [];
      if (deltas.length === 0) {
        deltaEl.innerHTML = '<div class="empty-state"><div class="empty-state-text">No rolling delta data available</div></div>';
      } else {
        const rows = deltas.slice(-20).map(d => {
          const cls = d.delta > 0 ? 'green' : d.delta < 0 ? 'red' : '';
          const arrow = d.delta > 0 ? '▲' : d.delta < 0 ? '▼' : '—';
          return `<div class="guardrail-row"><span class="guardrail-label">${formatTimestamp(d.ts)}</span><span class="guardrail-value ${cls}">${arrow} ${formatNumber(d.delta, 4)}</span></div>`;
        }).join('');
        deltaEl.innerHTML = `<div style="max-height:200px;overflow-y:auto">${rows}</div>`;
      }
    }

    const weightsEl = document.getElementById('macro-country-weights');
    if (weightsEl) {
      const weights = mt.country_weights || [];
      if (weights.length === 0) {
        weightsEl.innerHTML = '<div class="empty-state"><div class="empty-state-text">No country weight data available</div></div>';
      } else {
        const header = '<div class="guardrail-row" style="font-weight:600;border-bottom:1px solid var(--border)"><span class="guardrail-label">Country</span><span style="flex:1;text-align:right;font-size:12px">Tariff Rate</span><span style="flex:1;text-align:right;font-size:12px">Weight %</span></div>';
        const rows = weights.map(w => {
          const barW = Math.min(w.weight_pct || 0, 100);
          return `<div class="guardrail-row"><span class="guardrail-label">${w.country || w.code}</span><span style="flex:1;text-align:right;font-size:13px">${formatNumber(w.tariff_rate, 2)}%</span><span style="flex:1;text-align:right;font-size:13px">${formatNumber(w.weight_pct, 1)}%</span></div><div style="height:3px;background:var(--bg-tertiary);border-radius:2px;margin-bottom:4px"><div style="height:3px;width:${barW}%;background:var(--accent-blue);border-radius:2px"></div></div>`;
        }).join('');
        weightsEl.innerHTML = header + rows;
      }
    }

    const heatmapEl = document.getElementById('macro-heatmap');
    if (heatmapEl) {
      const corr = mt.correlations || {};
      const keys = Object.keys(corr);
      if (keys.length === 0) {
        heatmapEl.innerHTML = '<div class="empty-state"><div class="empty-state-text">No correlation data available</div></div>';
      } else {
        const rows = keys.map(k => {
          const v = corr[k];
          const abs = Math.abs(v);
          const bg = abs > 0.7 ? 'rgba(248,81,73,0.3)' : abs > 0.3 ? 'rgba(210,153,34,0.3)' : 'rgba(63,185,80,0.2)';
          const label = k.replace(/_/g, ' ').replace('tariff delta vs ', '');
          return `<div class="guardrail-row" style="background:${bg};border-radius:4px;margin-bottom:4px;padding:6px 8px"><span class="guardrail-label" style="font-size:12px;text-transform:capitalize">${label}</span><span class="guardrail-value" style="font-size:14px;font-weight:600">${formatNumber(v, 4)}</span></div>`;
        }).join('');
        heatmapEl.innerHTML = rows;
      }
    }
  }

  function renderMarketsTab(data) {
    if (data.latest) {
      const tbody = document.getElementById('markets-tbody');
      if (tbody) {
        tbody.innerHTML = '';
        data.latest.forEach(m => {
          const tr = document.createElement('tr');
          tr.innerHTML = `<td>${m.symbol || '--'}</td><td>${m.source || '--'}</td><td>${formatPrice(m.price)}</td><td>${formatNumber(m.confidence, 2)}</td><td>${formatTimestamp(m.ts)}</td>`;
          tbody.appendChild(tr);
        });
      }
      const latestTs = data.latest.length > 0 ? data.latest[0].ts : null;
      renderFreshnessBadge('markets-freshness', latestTs);
    }

    if (data.funding && data.funding.funding_rates && window._fundingChart) {
      const rates = data.funding.funding_rates;
      Charts.updateChart(window._fundingChart, {
        labels: rates.map(r => r.symbol || r.market || 'Unknown'),
        datasets: [{
          data: rates.map(r => (r.funding_rate || r.rate || 0) * 10000),
          backgroundColor: rates.map(r => {
            const v = r.funding_rate || r.rate || 0;
            return v >= 0 ? 'rgba(63, 185, 80, 0.7)' : 'rgba(248, 81, 73, 0.7)';
          }),
        }],
      });
    }

    if (data.carry) {
      const panel = document.getElementById('carry-panel');
      if (panel) {
        const scores = data.carry.scores || [];
        if (scores.length === 0) {
          panel.innerHTML = '<div style="font-size:13px;color:var(--text-muted);text-align:center;padding:20px">No carry data</div>';
        } else {
          panel.innerHTML = scores.map(s => {
            const cls = s.annualized_carry > 0 ? 'green' : s.annualized_carry < 0 ? 'red' : '';
            return `<div class="guardrail-row"><span class="guardrail-label">${s.market || s.symbol || '--'}</span><span class="guardrail-value ${cls}">${formatNumber(s.annualized_carry * 100, 2)}% APR</span></div>`;
          }).join('');
        }
      }
    }

    if (data.microstructure) {
      const ms = data.microstructure;
      const obEl = document.getElementById('ob-imbalance');
      const biasEl = document.getElementById('ob-bias');
      const basisEl = document.getElementById('basis-info');
      if (obEl) {
        obEl.textContent = formatNumber(ms.ob_imbalance, 4);
        obEl.className = 'card-value ' + (ms.ob_imbalance > 0.1 ? 'positive' : ms.ob_imbalance < -0.1 ? 'negative' : '');
      }
      if (biasEl) biasEl.textContent = ms.ob_bias || '--';
      if (basisEl) {
        if (ms.basis_bps !== undefined) {
          basisEl.innerHTML = `<div><strong>${formatNumber(ms.basis_bps, 2)} bps</strong> basis</div><div style="margin-top:4px">${ms.basis_opportunity || 'None'}</div>`;
        }
      }
    }

    if (data.integrity) {
      const el = document.getElementById('integrity-detail');
      const badge = document.getElementById('price-integrity-badge');
      if (el) {
        const devs = data.integrity.deviations || {};
        const entries = Object.entries(devs);
        if (entries.length === 0) {
          el.innerHTML = `<span class="badge badge-green">${data.integrity.status || 'OK'}</span> ${data.integrity.reason || ''}`;
        } else {
          el.innerHTML = entries.map(([venue, pct]) => {
            const cls = Math.abs(pct) > 1 ? 'badge-red' : Math.abs(pct) > 0.5 ? 'badge-yellow' : 'badge-green';
            return `<span class="badge ${cls}" style="margin:2px">${venue}: ${formatNumber(pct, 3)}%</span>`;
          }).join('');
        }
      }
      if (badge) {
        const st = (data.integrity.status || 'OK').toUpperCase();
        badge.textContent = 'Price: ' + st;
        badge.className = 'integrity-badge ' + (st === 'OK' ? 'ok' : st === 'WARNING' ? 'warn' : 'alert');
      }
    }

    if (data.solanaQuality) {
      const sq = data.solanaQuality;
      const scoreEl = document.getElementById('solana-quality-score');
      const riskEl = document.getElementById('solana-slippage-risk');
      const latEl = document.getElementById('solana-rpc-latency');
      const congEl = document.getElementById('solana-congestion');
      const routeEl = document.getElementById('solana-route-info');
      if (scoreEl) {
        scoreEl.textContent = formatNumber(sq.execution_quality_score, 1);
        scoreEl.className = 'card-value ' + (sq.execution_quality_score >= 80 ? 'green' : sq.execution_quality_score >= 50 ? 'yellow' : 'red');
      }
      if (riskEl) riskEl.textContent = 'Slippage: ' + (sq.slippage_risk || '--');
      if (latEl) latEl.textContent = formatNumber(sq.components?.latency_score || 0, 0) + ' ms';
      if (congEl) congEl.textContent = sq.congestion_warning ? 'CONGESTED' : 'Normal';
      if (routeEl) {
        const c = sq.components || {};
        routeEl.innerHTML = `<div>Spread Score: ${formatNumber(c.spread_score, 1)}</div><div>Impact Score: ${formatNumber(c.impact_score, 1)}</div><div>Depth Score: ${formatNumber(c.depth_score, 1)}</div>`;
      }
    }

    if (data.fundingArb) {
      const fa = data.fundingArb;
      const panel = document.getElementById('funding-arb-panel');
      if (panel) {
        const sigCls = fa.arb_signal === 'none' ? 'blue' : 'green';
        panel.innerHTML = `
          <div class="metric-row">
            <div class="metric-box" style="flex:1"><div class="metric-label">Signal</div><div class="metric-value ${sigCls}" style="font-size:14px">${fa.arb_signal || 'none'}</div></div>
            <div class="metric-box" style="flex:1"><div class="metric-label">Spread</div><div class="metric-value" style="font-size:16px">${formatNumber(fa.spread_bps, 2)} bps</div></div>
            <div class="metric-box" style="flex:1"><div class="metric-label">Persistence</div><div class="metric-value" style="font-size:16px">${formatNumber(fa.persistence_minutes, 0)} min</div></div>
            <div class="metric-box" style="flex:1"><div class="metric-label">Net Carry</div><div class="metric-value" style="font-size:16px">${formatNumber(fa.expected_net_carry * 100, 2)}%</div></div>
          </div>
        `;
      }
    }

    if (data.basis) {
      const b = data.basis;
      const panel = document.getElementById('basis-monitor-panel');
      if (panel) {
        panel.innerHTML = `
          <div class="metric-row">
            <div class="metric-box" style="flex:1"><div class="metric-label">HL-Spot Basis</div><div class="metric-value" style="font-size:14px">${formatNumber(b.hl_spot_basis_bps, 2)} bps</div></div>
            <div class="metric-box" style="flex:1"><div class="metric-label">Drift-Spot Basis</div><div class="metric-value" style="font-size:14px">${formatNumber(b.drift_spot_basis_bps, 2)} bps</div></div>
            <div class="metric-box" style="flex:1"><div class="metric-label">HL-Drift Spread</div><div class="metric-value" style="font-size:14px">${formatNumber(b.hl_drift_spread_bps, 2)} bps</div></div>
            <div class="metric-box" style="flex:1"><div class="metric-label">Ann. Basis</div><div class="metric-value" style="font-size:14px">${formatNumber(b.annualized_basis_bps, 2)} bps</div></div>
            <div class="metric-box" style="flex:1"><div class="metric-label">Net Carry</div><div class="metric-value" style="font-size:14px">${formatNumber(b.net_carry, 4)}</div></div>
          </div>
        `;
      }
    }
  }

  function renderDivergenceTab(data) {
    if (data.spreads && data.spreads.length > 0) {
      renderFreshnessBadge('divergence-freshness', data.spreads[0].ts || new Date().toISOString());
    }
    if (data.spreads && window._divergenceChart) {
      Charts.updateChart(window._divergenceChart, {
        labels: data.spreads.map(s => `${s.venue_a}/${s.venue_b}`),
        datasets: [{
          data: data.spreads.map(s => s.spread_bps),
          backgroundColor: data.spreads.map(s => {
            const abs = Math.abs(s.spread_bps);
            if (abs > 50) return 'rgba(248, 81, 73, 0.7)';
            if (abs > 20) return 'rgba(210, 153, 34, 0.7)';
            return 'rgba(63, 185, 80, 0.7)';
          }),
        }],
      });

      const tbody = document.getElementById('spreads-tbody');
      if (tbody) {
        tbody.innerHTML = '';
        data.spreads.forEach(s => {
          const abs = Math.abs(s.spread_bps);
          const cls = abs > 50 ? 'badge-red' : abs > 20 ? 'badge-yellow' : 'badge-green';
          const tr = document.createElement('tr');
          tr.innerHTML = `<td>${s.market || '--'}</td><td>${s.venue_a}</td><td>${formatPrice(s.price_a)}</td><td>${s.venue_b}</td><td>${formatPrice(s.price_b)}</td><td><span class="badge ${cls}">${formatNumber(s.spread_bps, 2)} bps</span></td>`;
          tbody.appendChild(tr);
        });
      }
    }

    if (data.alerts) {
      const container = document.getElementById('divergence-alerts');
      if (container) {
        container.innerHTML = '';
        if (data.alerts.length === 0) {
          container.innerHTML = '<div class="empty-state"><div class="empty-state-text">No divergence alerts</div></div>';
        } else {
          data.alerts.forEach(a => {
            const div = document.createElement('div');
            div.className = `alert-item ${a.severity || 'info'}`;
            div.innerHTML = `<span class="alert-message">${a.message}</span><span class="alert-time">${formatTimestamp(a.ts)}</span>`;
            container.appendChild(div);
          });
        }
      }
    }
  }

  function renderStablecoinsTab(data) {
    if (data.health) {
      const h = data.health;
      const stables = h.stablecoins || [];
      stables.forEach(s => {
        const sym = (s.symbol || '').toLowerCase();
        const box = document.getElementById('stable-' + sym);
        if (box) {
          const depeg = Math.abs(s.depeg_bps || 0);
          const color = depeg > 50 ? 'red' : depeg > 10 ? 'yellow' : 'green';
          box.querySelector('.metric-value').textContent = '$' + formatNumber(s.price, 4);
          box.querySelector('.metric-value').className = 'metric-value ' + color;
          box.querySelector('.metric-sublabel').textContent = formatNumber(depeg, 1) + ' bps depeg';
        }
      });

      const heatTbody = document.querySelector('#depeg-heatmap tbody');
      if (heatTbody) {
        heatTbody.innerHTML = '';
        stables.forEach(s => {
          const depeg = Math.abs(s.depeg_bps || 0);
          const cls = depeg > 50 ? 'badge-red' : depeg > 10 ? 'badge-yellow' : 'badge-green';
          const status = depeg > 50 ? 'DEPEGGING' : depeg > 10 ? 'STRESSED' : 'STABLE';
          const tr = document.createElement('tr');
          tr.innerHTML = `<td>${s.symbol}</td><td>${formatPrice(s.price)}</td><td>${formatNumber(depeg, 1)}</td><td><span class="badge ${cls}">${status}</span></td>`;
          heatTbody.appendChild(tr);
        });
      }

      const stressPanel = document.getElementById('stable-stress-panel');
      if (stressPanel) {
        const stress = h.stress_level || 'LOW';
        const pegBreak = h.peg_break_probability || 0;
        const stressCls = stress === 'HIGH' || stress === 'CRITICAL' ? 'red' : stress === 'MEDIUM' ? 'yellow' : 'green';
        stressPanel.innerHTML = `
          <div class="guardrail-row"><span class="guardrail-label">Stress Level</span><span class="guardrail-value ${stressCls}">${stress}</span></div>
          <div class="guardrail-row"><span class="guardrail-label">Peg Break Probability</span><span class="guardrail-value">${formatNumber(pegBreak * 100, 2)}%</span></div>
          <div class="guardrail-row"><span class="guardrail-label">Composite Score</span><span class="guardrail-value">${formatNumber(h.composite_health, 4)}</span></div>
        `;
      }
    }

    if (data.alerts) {
      const container = document.getElementById('stable-alerts');
      if (container) {
        container.innerHTML = '';
        if (data.alerts.length === 0) {
          container.innerHTML = '<div class="empty-state"><div class="empty-state-text">No stablecoin alerts</div></div>';
        } else {
          data.alerts.forEach(a => {
            const div = document.createElement('div');
            div.className = `alert-item ${a.severity || 'warning'}`;
            div.innerHTML = `<span class="alert-message">${a.message || a.alert_type || '--'}</span><span class="alert-time">${formatTimestamp(a.ts)}</span>`;
            container.appendChild(div);
          });
        }
      }
    }

    if (data.stableFlow) {
      const panel = document.getElementById('stable-flow-panel');
      if (panel) {
        const sf = data.stableFlow;
        const momCls = sf.stable_flow_momentum > 0.2 ? 'green' : sf.stable_flow_momentum < -0.2 ? 'red' : 'blue';
        const indCls = sf.risk_on_off_indicator === 'risk_on' ? 'green' : sf.risk_on_off_indicator === 'risk_off' ? 'red' : 'blue';
        const drivers = (sf.drivers || []).map(d => `<div style="font-size:12px;color:var(--text-muted);margin-top:2px">- ${d}</div>`).join('');
        panel.innerHTML = `
          <div class="metric-row">
            <div class="metric-box" style="flex:1"><div class="metric-label">Flow Momentum</div><div class="metric-value ${momCls}" style="font-size:18px">${formatNumber(sf.stable_flow_momentum, 4)}</div></div>
            <div class="metric-box" style="flex:1"><div class="metric-label">Risk Signal</div><div class="metric-value ${indCls}" style="font-size:14px">${sf.risk_on_off_indicator || 'neutral'}</div></div>
          </div>
          <div style="margin-top:8px">${drivers}</div>
        `;
      }
    }
  }

  function renderStrategyTab(data) {
    const container = document.getElementById('rules-container');
    if (!container) return;
    container.innerHTML = '';

    if (data.evaluation && data.evaluation.length > 0) {
      data.evaluation.forEach(rule => {
        const div = document.createElement('div');
        div.className = 'rule-card';
        const actionColor = rule.action_type === 'open_short' || rule.action_type === 'reduce' || rule.action_type === 'rotate_to_stables' ? 'red' : rule.action_type === 'open_long' ? 'green' : 'blue';
        div.innerHTML = `
          <div class="rule-name">${rule.rule_name}</div>
          <div class="rule-action"><span class="badge badge-${actionColor}">${rule.action_type}</span> ${rule.venue} ${rule.market} ${rule.side} ${rule.size > 0 ? formatNumber(rule.size, 4) : ''}</div>
          <div class="rule-reason">${rule.reason}</div>
        `;
        container.appendChild(div);
      });
    } else {
      container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">&#9889;</div><div class="empty-state-text">No active rule signals</div></div>';
    }

    if (data.status && data.status.rules) {
      const listEl = document.getElementById('rules-list');
      if (listEl) {
        listEl.innerHTML = '';
        data.status.rules.forEach(r => {
          const div = document.createElement('div');
          div.className = 'rule-card';
          div.innerHTML = `<div class="rule-name">${r.name}</div><div class="rule-action"><span class="badge badge-blue">${r.action_type}</span></div><div class="rule-reason">${r.explanation || ''}</div>`;
          listEl.appendChild(div);
        });
      }
    }

    if (data.adaptiveWeights) {
      const panel = document.getElementById('adaptive-weights-panel');
      if (panel) {
        const aw = data.adaptiveWeights;
        const wt = aw.weights || {};
        const adjustments = (aw.adjustments || []).map(a => `<div style="font-size:12px;color:var(--text-muted);margin-top:2px">- ${a}</div>`).join('');
        panel.innerHTML = `
          <div class="metric-row">
            ${Object.entries(wt).map(([k, v]) => `<div class="metric-box" style="flex:1"><div class="metric-label">${k}</div><div class="metric-value blue" style="font-size:16px">${formatNumber(v * 100, 1)}%</div></div>`).join('')}
          </div>
          <div style="margin-top:6px;font-size:12px;color:var(--text-secondary)">Adaptive: ${aw.adaptive_enabled ? 'ON' : 'OFF'}</div>
          ${adjustments}
        `;
      }
    }

    if (data.portfolio) {
      const panel = document.getElementById('portfolio-proposal-panel');
      if (panel) {
        const p = data.portfolio;
        const alloc = p.allocation || {};
        const reasoning = (p.reasoning || []).map(r => `<div style="font-size:12px;color:var(--text-muted);margin-top:2px">- ${r}</div>`).join('');
        panel.innerHTML = `
          <div style="margin-bottom:8px;font-size:12px;color:var(--text-secondary)">Method: ${p.method || 'risk_parity'}</div>
          <div class="metric-row">
            ${Object.entries(alloc).map(([k, v]) => {
              const pct = (v * 100).toFixed(1);
              const barW = Math.min(pct, 100);
              return `<div class="metric-box" style="flex:1"><div class="metric-label">${k.replace(/_/g, ' ')}</div><div class="metric-value" style="font-size:14px">${pct}%</div><div style="height:4px;background:var(--bg-tertiary);border-radius:2px;margin-top:4px"><div style="height:4px;width:${barW}%;background:var(--accent-blue);border-radius:2px"></div></div></div>`;
            }).join('')}
          </div>
          <div style="margin-top:8px">${reasoning}</div>
        `;
      }
    }
  }

  function renderExecutionTab(data) {
    if (data.positions) {
      const tbody = document.getElementById('positions-tbody');
      if (tbody) {
        tbody.innerHTML = '';
        const live = data.positions.live_positions || [];
        const db = data.positions.db_positions || [];
        const all = [...live, ...db];
        if (all.length === 0) {
          tbody.innerHTML = '<tr><td colspan="6" class="empty-state-text" style="text-align:center;padding:20px">No positions</td></tr>';
        } else {
          all.forEach(p => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${p.venue || '--'}</td><td>${p.market || p.symbol || '--'}</td><td><span class="badge ${p.side === 'long' ? 'badge-green' : 'badge-red'}">${p.side || '--'}</span></td><td>${formatNumber(p.size, 4)}</td><td>${formatPrice(p.entry_price || p.price)}</td><td>${formatTimestamp(p.ts || p.opened_at)}</td>`;
            tbody.appendChild(tr);
          });
        }
      }
    }

    if (data.trades) {
      const tbody = document.getElementById('trades-tbody');
      if (tbody) {
        tbody.innerHTML = '';
        const trades = data.trades.trades || [];
        if (trades.length === 0) {
          tbody.innerHTML = '<tr><td colspan="7" class="empty-state-text" style="text-align:center;padding:20px">No paper trades</td></tr>';
        } else {
          trades.forEach(t => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${t.venue || '--'}</td><td>${t.market || '--'}</td><td><span class="badge ${t.side === 'buy' ? 'badge-green' : 'badge-red'}">${t.side || '--'}</span></td><td>${formatNumber(t.size, 4)}</td><td>${formatPrice(t.price)}</td><td><span class="badge badge-blue">${t.status || '--'}</span></td><td>${formatTimestamp(t.ts || t.created_at)}</td>`;
            tbody.appendChild(tr);
          });
        }
      }
    }

    if (data.eqi) {
      const panel = document.getElementById('eqi-panel');
      if (panel) {
        const e = data.eqi;
        const scoreCls = e.eqi_score >= 80 ? 'green' : e.eqi_score >= 50 ? 'yellow' : 'red';
        const anomalies = (e.anomalies || []).map(a => `<div style="font-size:12px;color:var(--accent-red);margin-top:2px">- ${a}</div>`).join('');
        panel.innerHTML = `
          <div class="metric-row">
            <div class="metric-box"><div class="metric-label">EQI Score</div><div class="metric-value ${scoreCls}">${formatNumber(e.eqi_score, 1)}</div></div>
            <div class="metric-box"><div class="metric-label">Latency p50</div><div class="metric-value">${formatNumber(e.latency_p50_ms, 0)} ms</div></div>
            <div class="metric-box"><div class="metric-label">Latency p95</div><div class="metric-value">${formatNumber(e.latency_p95_ms, 0)} ms</div></div>
            <div class="metric-box"><div class="metric-label">Avg Slippage</div><div class="metric-value">${formatNumber(e.avg_slippage_bps, 2)} bps</div></div>
            <div class="metric-box"><div class="metric-label">Fill Count</div><div class="metric-value blue">${e.fill_count || 0}</div></div>
          </div>
          ${anomalies}
        `;
      }
    }
  }

  function renderRiskTab(data) {
    if (data.status) {
      const s = data.status;
      const banner = document.getElementById('throttle-banner');
      if (banner) {
        if (s.throttle_active) {
          banner.className = 'throttle-banner';
          banner.innerHTML = `<span>&#9888;</span> <strong>THROTTLE ACTIVE</strong> &mdash; ${s.throttle_reason || 'Risk limits reached'}`;
        } else {
          banner.className = 'throttle-banner inactive';
          banner.innerHTML = `<span>&#10003;</span> <strong>THROTTLE OFF</strong> &mdash; Trading enabled`;
        }
      }

      const setVal = (id, val, cls) => {
        const el = document.getElementById(id);
        if (el) {
          el.textContent = val;
          if (cls) el.className = 'metric-value ' + cls;
        }
      };
      setVal('risk-leverage', formatNumber(s.current_leverage, 2) + 'x');
      setVal('risk-margin', formatNumber(s.margin_usage * 100, 1) + '%');
      setVal('risk-pnl', '$' + formatNumber(s.daily_pnl, 2), classForValue(s.daily_pnl));
    }

    if (data.guardrails) {
      const g = data.guardrails;
      const container = document.getElementById('guardrails-container');
      if (container) {
        container.innerHTML = '';
        const items = [
          ['Max Leverage', g.max_leverage + 'x'],
          ['Max Margin Usage', (g.max_margin_usage * 100).toFixed(0) + '%'],
          ['Max Daily Loss', '$' + g.max_daily_loss],
          ['Cooldown', g.cooldown_seconds + 's'],
          ['Execution Mode', g.execution_mode || 'paper'],
        ];
        items.forEach(([label, value]) => {
          const div = document.createElement('div');
          div.className = 'guardrail-row';
          div.innerHTML = `<span class="guardrail-label">${label}</span><span class="guardrail-value">${value}</span>`;
          container.appendChild(div);
        });
      }
    }

    if (data.stressResult) {
      const r = data.stressResult;
      const container = document.getElementById('stress-result');
      if (container) {
        container.innerHTML = `
          <div class="card" style="margin-top:12px">
            <div class="card-header"><span class="card-title">Stress Test Result: ${r.scenario || '--'}</span></div>
            <div class="metric-row">
              <div class="metric-box"><div class="metric-label">Total P&amp;L Impact</div><div class="metric-value ${classForValue(r.total_pnl_impact)}">$${formatNumber(r.total_pnl_impact, 2)}</div></div>
              <div class="metric-box"><div class="metric-label">Max Drawdown</div><div class="metric-value red">$${formatNumber(r.max_drawdown, 2)}</div></div>
              <div class="metric-box"><div class="metric-label">Margin Call</div><div class="metric-value ${r.margin_call ? 'red' : 'green'}">${r.margin_call ? 'YES' : 'NO'}</div></div>
            </div>
          </div>
        `;
      }
    }

    if (data.mcResult) {
      renderMCResult(data.mcResult);
    }

    if (data.heatmap) {
      const panel = document.getElementById('liquidation-heatmap-panel');
      if (panel) {
        const hm = data.heatmap;
        const grid = hm.grid || {};
        const leverages = hm.leverage_levels || [];
        const drops = hm.price_drops_pct || hm.price_drops || [];
        if (leverages.length === 0 || drops.length === 0) {
          panel.innerHTML = '<div class="empty-state"><div class="empty-state-text">No heatmap data</div></div>';
        } else {
          let html = '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:11px">';
          html += '<tr><th style="padding:4px;text-align:left">Lev \\ Drop</th>';
          drops.forEach(d => { html += `<th style="padding:4px;text-align:center">${d}%</th>`; });
          html += '</tr>';
          leverages.forEach(lev => {
            html += `<tr><td style="padding:4px;font-weight:bold">${lev}x</td>`;
            const row = grid[String(lev)] || {};
            drops.forEach(drop => {
              const prob = row[String(drop)] || 0;
              const pct = (prob * 100).toFixed(0);
              const bg = prob >= 0.8 ? 'rgba(248,81,73,0.8)' : prob >= 0.5 ? 'rgba(248,81,73,0.5)' : prob >= 0.2 ? 'rgba(227,179,65,0.4)' : 'rgba(63,185,80,0.2)';
              html += `<td style="padding:4px;text-align:center;background:${bg};border:1px solid var(--border)">${pct}%</td>`;
            });
            html += '</tr>';
          });
          html += '</table></div>';
          panel.innerHTML = html;
        }
      }
    }

    if (data.analogs) {
      const panel = document.getElementById('regime-replay-panel');
      if (panel && data.analogs.analogs) {
        const analogs = data.analogs.analogs || [];
        if (analogs.length === 0) {
          panel.innerHTML = '<div class="empty-state"><div class="empty-state-text">No regime analogs found</div></div>';
        } else {
          const dist = data.analogs.outcome_distribution || {};
          let html = '<div class="metric-row">';
          html += `<div class="metric-box"><div class="metric-label">Avg 4h Return</div><div class="metric-value ${classForValue(dist.avg_return_4h)}">${formatNumber((dist.avg_return_4h || 0) * 100, 2)}%</div></div>`;
          html += `<div class="metric-box"><div class="metric-label">Avg 24h Return</div><div class="metric-value ${classForValue(dist.avg_return_24h)}">${formatNumber((dist.avg_return_24h || 0) * 100, 2)}%</div></div>`;
          html += `<div class="metric-box"><div class="metric-label">Win Rate 4h</div><div class="metric-value">${formatNumber((dist.win_rate_4h || 0) * 100, 1)}%</div></div>`;
          html += `<div class="metric-box"><div class="metric-label">Sample Count</div><div class="metric-value blue">${dist.count || 0}</div></div>`;
          html += '</div>';
          panel.innerHTML = html;
        }
      }
    }
  }

  function renderMCResult(mc) {
    const container = document.getElementById('mc-result');
    if (!container) return;
    container.innerHTML = `
      <div class="metric-row" style="margin-top:12px">
        <div class="metric-box"><div class="metric-label">VaR (95%)</div><div class="metric-value red">$${formatNumber(mc.var_95, 2)}</div></div>
        <div class="metric-box"><div class="metric-label">CVaR (95%)</div><div class="metric-value red">$${formatNumber(mc.cvar_95, 2)}</div></div>
        <div class="metric-box"><div class="metric-label">Mean P&amp;L</div><div class="metric-value ${classForValue(mc.mean_pnl)}">$${formatNumber(mc.mean_pnl, 2)}</div></div>
        <div class="metric-box"><div class="metric-label">Paths</div><div class="metric-value blue">${mc.n_paths || '--'}</div></div>
      </div>
    `;

    if (mc.distribution && window._mcChart) {
      const wrap = document.getElementById('mc-chart-wrap');
      if (wrap) wrap.style.display = 'block';
      Charts.updateChart(window._mcChart, {
        labels: mc.distribution.bins || mc.distribution.map((_, i) => i),
        datasets: [{
          data: mc.distribution.counts || mc.distribution,
        }],
      });
    }
  }

  function renderFeedStatus(data) {
    const panel = document.getElementById('feed-status-panel');
    if (!panel) return;
    const feeds = data.feeds || [];
    if (feeds.length === 0) {
      panel.innerHTML = '<div class="empty-state"><div class="empty-state-text">No feed data available</div></div>';
      return;
    }
    const statusBadge = (s) => {
      const cls = s === 'ok' ? 'badge-green' : s === 'warning' ? 'badge-yellow' : s === 'fallback' ? 'badge-blue' : 'badge-red';
      return `<span class="badge ${cls}">${s.toUpperCase()}</span>`;
    };
    const formatAge = (sec) => {
      if (sec === null || sec === undefined) return '--';
      if (sec < 60) return Math.round(sec) + 's';
      if (sec < 3600) return Math.round(sec / 60) + 'm';
      if (sec < 86400) return (sec / 3600).toFixed(1) + 'h';
      return (sec / 86400).toFixed(1) + 'd';
    };
    let html = '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12px">';
    html += '<thead><tr><th style="padding:6px 8px;text-align:left">Feed</th><th style="padding:6px 8px;text-align:center">Status</th><th style="padding:6px 8px;text-align:center">Age</th><th style="padding:6px 8px;text-align:center">Last Update</th><th style="padding:6px 8px;text-align:center">Auth</th></tr></thead><tbody>';
    feeds.forEach(f => {
      const ts = f.last_update_ts ? formatTimestamp(f.last_update_ts) : '--';
      const auth = f.is_authoritative ? '<span class="badge badge-purple" style="font-size:10px">AUTH</span>' : '';
      html += `<tr style="border-bottom:1px solid var(--border-color)"><td style="padding:6px 8px;font-weight:500">${f.name}</td><td style="padding:6px 8px;text-align:center">${statusBadge(f.status)}</td><td style="padding:6px 8px;text-align:center">${formatAge(f.age_seconds)}</td><td style="padding:6px 8px;text-align:center;font-family:var(--font-mono);font-size:11px">${ts}</td><td style="padding:6px 8px;text-align:center">${auth}</td></tr>`;
    });
    html += '</tbody></table></div>';
    const summary = `<div style="margin-top:8px;font-size:11px;color:var(--text-muted)">${data.ok_count}/${data.total} feeds healthy &mdash; Overall: <span class="badge ${data.status === 'ok' ? 'badge-green' : data.status === 'degraded' ? 'badge-yellow' : 'badge-red'}" style="font-size:10px">${(data.status || 'unknown').toUpperCase()}</span></div>`;
    panel.innerHTML = html + summary;
  }

  function renderAgentsTab(data) {
    if (data.signals) {
      const sigs = data.signals.signals || data.signals;
      const sigList = Array.isArray(sigs) ? sigs : [];
      const container = document.getElementById('agent-signals-container');
      const countEl = document.getElementById('agent-signal-count');
      const tsEl = document.getElementById('agent-last-updated');
      const agentCountEl = document.getElementById('agent-count');
      if (countEl) countEl.textContent = sigList.length;
      if (tsEl) tsEl.textContent = formatTimestamp(data.signals.ts || null);
      if (agentCountEl) agentCountEl.textContent = data.signals.agent_count || 6;

      if (container) {
        container.innerHTML = '';
        if (sigList.length === 0) {
          container.innerHTML = '<div class="empty-state"><div class="empty-state-text">No active agent signals</div></div>';
        } else {
          sigList.forEach((sig, idx) => {
            const div = document.createElement('div');
            const severityCls = sig.severity === 'high' ? 'red' : sig.severity === 'medium' ? 'yellow' : 'green';
            const dirCls = sig.direction === 'bullish' ? 'green' : sig.direction === 'bearish' ? 'red' : 'blue';
            const conf = sig.confidence || 0;
            const confPct = (conf * 100).toFixed(0);
            const confCls = conf >= 0.85 ? 'red' : conf >= 0.75 ? 'yellow' : 'green';
            const actionBadge = sig.proposed_action ? `<span class="badge badge-${sig.proposed_action === 'block_execution' ? 'red' : sig.proposed_action === 'reduce_size' ? 'yellow' : 'blue'}">${(sig.proposed_action || '').replace(/_/g, ' ')}</span>` : '';
            const reasonId = 'agent-reason-' + idx;
            div.className = 'agent-signal-card';
            div.innerHTML = `
              <div class="agent-signal-header">
                <span class="badge badge-purple">${sig.agent || '--'}</span>
                <span class="badge badge-${severityCls}">${sig.severity || 'low'}</span>
                <span class="badge badge-${dirCls}">${sig.direction || 'neutral'}</span>
                ${actionBadge}
                <span class="agent-confidence-badge ${confCls}" title="Confidence">${confPct}%</span>
              </div>
              <div class="agent-signal-action">${sig.signal || sig.action || '--'}</div>
              <div class="agent-signal-reason-toggle" onclick="document.getElementById('${reasonId}').classList.toggle('expanded')">
                <span class="agent-toggle-icon">&#9654;</span> Reasoning
              </div>
              <div id="${reasonId}" class="agent-signal-reason-detail">${sig.reason || '--'}</div>
              <div class="agent-signal-meta">
                <span>Signal: ${formatTimestamp(sig.ts)}</span>
                <span>Data: ${formatTimestamp(sig.data_ts_used)}</span>
              </div>
            `;
            container.appendChild(div);
          });
        }
      }
    }

    if (data.registry) {
      const container = document.getElementById('agent-registry');
      if (container) {
        container.innerHTML = '';
        (data.registry.agents || []).forEach(agent => {
          const div = document.createElement('div');
          div.className = 'agent-registry-card';
          const statusCls = agent.status === 'active' ? 'green' : 'yellow';
          div.innerHTML = `
            <div class="agent-registry-header">
              <span class="agent-registry-name">${(agent.name || '').replace(/_/g, ' ')}</span>
              <span class="badge badge-${statusCls}">${agent.status || 'active'}</span>
            </div>
            <div class="agent-registry-desc">${agent.description || ''}</div>
          `;
          container.appendChild(div);
        });
      }
    }
  }

  function getEventClass(eventType) {
    if (!eventType) return 'event-info';
    const t = eventType.toUpperCase();
    if (t.includes('FILL') || t.includes('TRADE') || t.includes('EXECUTED')) return 'event-fill';
    if (t.includes('ERROR') || t.includes('FAIL')) return 'event-error';
    if (t.includes('ALERT') || t.includes('SHOCK') || t.includes('DIVERGENCE') || t.includes('WARN') || t.includes('DEPEG') || t.includes('STRESS') || t.includes('BREACH') || t.includes('DISLOCATION')) return 'event-alert';
    if (t.includes('ORDER') || t.includes('POSITION') || t.includes('AGENT')) return 'event-trade';
    return 'event-info';
  }

  function getTypeClass(eventType) {
    if (!eventType) return 'info';
    const t = eventType.toUpperCase();
    if (t.includes('FILL') || t.includes('TRADE') || t.includes('EXECUTED')) return 'fill';
    if (t.includes('ERROR') || t.includes('FAIL')) return 'error';
    if (t.includes('ALERT') || t.includes('SHOCK') || t.includes('DIVERGENCE') || t.includes('WARN') || t.includes('DEPEG') || t.includes('STRESS') || t.includes('BREACH') || t.includes('DISLOCATION')) return 'alert';
    if (t.includes('ORDER') || t.includes('POSITION') || t.includes('AGENT')) return 'trade';
    return 'info';
  }

  function addEventToTimeline(event, isNew = false) {
    const body = document.getElementById('timeline-body');
    if (!body) return;

    const div = document.createElement('div');
    div.className = `timeline-event ${getEventClass(event.event_type)}${isNew ? ' new' : ''}`;

    const payload = event.payload || {};
    const msg = payload.message || event.message || JSON.stringify(payload).substring(0, 120);

    div.innerHTML = `
      <span class="timeline-ts">${formatTimestamp(event.ts)}</span>
      <span class="timeline-type ${getTypeClass(event.event_type)}">${event.event_type || 'INFO'}</span>
      <span class="timeline-msg" title="${msg}">${msg}</span>
      <span class="timeline-source">${event.source || '--'}</span>
    `;

    body.prepend(div);

    while (body.children.length > 50) {
      body.removeChild(body.lastChild);
    }
  }

  function renderTimeline(events) {
    const body = document.getElementById('timeline-body');
    if (!body) return;
    body.innerHTML = '';
    events.forEach(e => addEventToTimeline(e, false));
  }

  function updateConnectionStatus(connected) {
    const badge = document.getElementById('connection-status');
    if (!badge) return;
    if (connected) {
      badge.className = 'status-badge connected';
      badge.innerHTML = '<span class="dot"></span> LIVE';
    } else {
      badge.className = 'status-badge disconnected';
      badge.innerHTML = '<span class="dot"></span> OFFLINE';
    }
  }

  return {
    formatTimestamp,
    formatNumber,
    formatPrice,
    renderFreshnessBadge,
    renderDecisionDataPanel,
    renderIndexTab,
    renderMarketsTab,
    renderDivergenceTab,
    renderStablecoinsTab,
    renderStrategyTab,
    renderExecutionTab,
    renderRiskTab,
    renderMCResult,
    renderAgentsTab,
    renderFeedStatus,
    addEventToTimeline,
    renderTimeline,
    updateConnectionStatus,
  };
})();
