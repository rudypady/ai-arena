const AGENTS_META = {
  gemini:     { color: '#6c63ff', label: 'Gemini',     model: 'Google Gemini 1.5 Pro', icon: '✦', strategy: 'Rastová (Tech + Krypto)' },
  gpt:        { color: '#10b981', label: 'GPT-4o',     model: 'OpenAI GPT-4o',         icon: '⬡', strategy: 'Diverzifikovaná' },
  claude:     { color: '#f59e0b', label: 'Claude',     model: 'Anthropic Claude 3.5',  icon: '◈', strategy: 'Konzervatívna (Value)' },
  perplexity: { color: '#ec4899', label: 'Perplexity', model: 'Perplexity Sonar',      icon: '◎', strategy: 'Momentum & Trendy' },
};

let chart = null;
let portfolioData = {};

// ---- INIT ----
async function init() {
  renderSkeletons();
  await refresh();
  setInterval(refresh, 30000);
}

function renderSkeletons() {
  const grid = document.getElementById('agentsGrid');
  grid.innerHTML = Object.keys(AGENTS_META).map(id => buildCard(id, null)).join('');
}

// ---- MAIN REFRESH ----
async function refresh() {
  try {
    const [status, performance, trades] = await Promise.all([
      fetch('/api/status').then(r => r.json()),
      fetch('/api/performance').then(r => r.json()),
      fetch('/api/trades').then(r => r.json()),
    ]);

    portfolioData = {};
    status.forEach(p => {
      if (p.agent && p.agent.id) portfolioData[p.agent.id] = p;
    });

    renderCards(portfolioData);
    renderChart(performance);
    renderTrades(trades);
    document.getElementById('lastUpdate').textContent = 'Aktualizované: ' + new Date().toLocaleTimeString('sk-SK');
  } catch (e) {
    console.error('Refresh error:', e);
    document.getElementById('lastUpdate').textContent = 'Chyba pripojenia';
  }
}

// ---- CARDS ----
function renderCards(data) {
  const grid = document.getElementById('agentsGrid');
  grid.innerHTML = Object.keys(AGENTS_META).map(id => buildCard(id, data[id])).join('');
}

function buildCard(id, data) {
  const m = AGENTS_META[id];
  const snap = data?.snapshot || {};
  const holdings = data?.holdings || [];
  const log = data?.latest_log || {};
  const total = snap.total_value ?? 100;
  const pnl = snap.pnl_percent ?? 0;
  const cash = snap.cash ?? 100;
  const holdVal = snap.holdings_value ?? 0;
  const isDemo = !log.strategy || log.strategy?.includes('DEMO') || log.reasoning?.includes('[DEMO]');
  const pnlClass = pnl >= 0 ? 'positive' : 'negative';
  const pnlSign = pnl >= 0 ? '+' : '';

  const holdingsHtml = holdings.length > 0
    ? holdings.slice(0, 4).map(h => {
        const cur = h.current_price || h.avg_buy_price || 0;
        const val = h.quantity * cur;
        const hp = h.avg_buy_price ? ((cur - h.avg_buy_price) / h.avg_buy_price * 100) : 0;
        const hpClass = hp >= 0 ? 'pos' : 'neg';
        const hpSign = hp >= 0 ? '+' : '';
        return `<div class="holding-item">
          <div>
            <div class="holding-ticker">${h.ticker}</div>
            <div class="holding-name">${(h.name||'').substring(0,18)}</div>
          </div>
          <div style="text-align:right">
            <div class="holding-value">€${val.toFixed(2)}</div>
            <div class="holding-pnl ${hpClass}">${hpSign}${hp.toFixed(1)}%</div>
          </div>
        </div>`;
      }).join('')
    : `<div class="no-holdings">Všetko v hotovosti</div>`;

  const reasoning = log.reasoning || log.strategy || '';
  const reasonShort = reasoning.replace(/\[DEMO\]/g, '').trim().substring(0, 180);

  return `<div class="agent-card" data-agent="${id}" style="--accent:${m.color}">
    <div class="card-header">
      <div class="agent-identity">
        <div class="agent-icon">${m.icon}</div>
        <div>
          <div class="agent-name">${m.label}</div>
          <div class="agent-model">${m.model}</div>
        </div>
      </div>
      <span class="${isDemo ? 'demo-badge' : 'live-badge'}">${isDemo ? 'DEMO' : 'LIVE'}</span>
    </div>

    <div class="portfolio-value">
      <div class="value-amount">€${total.toFixed(2)}</div>
      <div class="value-pnl ${pnlClass}">${pnlSign}${pnl.toFixed(2)}% od štartu</div>
    </div>

    <div class="cash-row">
      <span>💵 Hotovosť: <strong>€${cash.toFixed(2)}</strong></span>
      <span>📊 Pozície: <strong>€${holdVal.toFixed(2)}</strong></span>
    </div>

    <div class="holdings-title">Portfólio</div>
    <div class="holdings-list">${holdingsHtml}</div>

    ${reasonShort ? `<div class="reasoning-box" title="${reasoning}">${reasonShort}</div>` : ''}
  </div>`;
}

// ---- CHART ----
function renderChart(performance) {
  const ctx = document.getElementById('performanceChart').getContext('2d');

  // Build time labels from all agents
  const allTimestamps = new Set();
  Object.values(performance).forEach(arr => arr.forEach(p => allTimestamps.add(p.timestamp)));
  const sortedTime = [...allTimestamps].sort();

  const datasets = Object.entries(AGENTS_META).map(([id, m]) => {
    const history = performance[id] || [];
    const valueMap = {};
    history.forEach(p => { valueMap[p.timestamp] = p.total_value; });
    const data = sortedTime.map(t => valueMap[t] ?? null);
    return {
      label: m.label,
      data,
      borderColor: m.color,
      backgroundColor: m.color + '18',
      borderWidth: 2,
      pointRadius: 2,
      pointHoverRadius: 5,
      fill: false,
      tension: 0.4,
      spanGaps: true,
    };
  });

  const labels = sortedTime.map(t => {
    const d = new Date(t);
    return d.toLocaleDateString('sk-SK', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  });

  if (chart) {
    chart.data.labels = labels;
    chart.data.datasets = datasets;
    chart.update();
    return;
  }

  chart = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          labels: { color: '#9999b8', font: { family: 'Inter', size: 12 }, boxWidth: 12 }
        },
        tooltip: {
          backgroundColor: 'rgba(13,13,30,0.95)',
          titleColor: '#e8e8f0',
          bodyColor: '#9999b8',
          borderColor: 'rgba(255,255,255,0.07)',
          borderWidth: 1,
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: €${ctx.parsed.y?.toFixed(2) ?? 'N/A'}`
          }
        }
      },
      scales: {
        x: {
          ticks: { color: '#6b6b8a', font: { size: 10 }, maxTicksLimit: 8 },
          grid: { color: 'rgba(255,255,255,0.04)' },
        },
        y: {
          ticks: {
            color: '#6b6b8a', font: { size: 10 },
            callback: v => `€${v.toFixed(0)}`
          },
          grid: { color: 'rgba(255,255,255,0.04)' },
        }
      }
    }
  });
}

// ---- TRADES ----
function renderTrades(trades) {
  const feed = document.getElementById('tradeFeed');
  if (!trades || trades.length === 0) {
    feed.innerHTML = '<div class="empty-feed">Žiadne obchody zatiaľ.<br>Spusti prvé kolo!</div>';
    return;
  }

  feed.innerHTML = trades.map(t => {
    const color = t.agent_color || '#888';
    const isBuy = t.action === 'buy';
    const time = new Date(t.timestamp).toLocaleTimeString('sk-SK', { hour: '2-digit', minute: '2-digit' });
    const date = new Date(t.timestamp).toLocaleDateString('sk-SK', { day: 'numeric', month: 'short' });
    return `<div class="trade-item">
      <div class="trade-agent-dot" style="background:${color};box-shadow:0 0 6px ${color}"></div>
      <div class="trade-info">
        <div class="trade-main">
          <span class="trade-action-badge ${isBuy ? 'buy-badge' : 'sell-badge'}">${isBuy ? 'KÚP' : 'PRED'}</span>
          <span class="trade-ticker">${t.ticker}</span>
        </div>
        <div class="trade-agent-name">${t.agent_name || t.agent_id}</div>
      </div>
      <div>
        <div class="trade-amount" style="color:${isBuy ? '#10b981' : '#ef4444'}">
          ${isBuy ? '+' : '-'}€${(t.amount_eur||0).toFixed(2)}
        </div>
        <span class="trade-time">${date} ${time}</span>
      </div>
    </div>`;
  }).join('');
}

// ---- ACTIONS ----
async function runRound() {
  const btn = document.getElementById('btnRunRound');
  const icon = document.getElementById('btnIcon');
  btn.disabled = true;
  icon.className = 'spinner';

  try {
    const r = await fetch('/api/round', { method: 'POST' });
    const data = await r.json();
    showToast('🚀 ' + data.message);

    // Poll for completion
    let attempts = 0;
    const poll = setInterval(async () => {
      attempts++;
      await refresh();
      if (attempts > 20) {
        clearInterval(poll);
        btn.disabled = false;
        icon.className = '';
        icon.textContent = '▶';
      }
    }, 5000);

    setTimeout(() => {
      clearInterval(poll);
      btn.disabled = false;
      icon.className = '';
      icon.textContent = '▶';
    }, 120000);

  } catch (e) {
    showToast('❌ Chyba: ' + e.message);
    btn.disabled = false;
    icon.className = '';
    icon.textContent = '▶';
  }
}

async function updatePrices() {
  const btn = document.getElementById('btnUpdatePrices');
  btn.disabled = true;
  btn.textContent = '↻ ...';
  try {
    await fetch('/api/update-prices', { method: 'POST' });
    await refresh();
    showToast('✅ Ceny aktualizované');
  } catch (e) {
    showToast('❌ Chyba aktualizácie cien');
  } finally {
    btn.disabled = false;
    btn.textContent = '↻ Ceny';
  }
}

async function resetSimulation() {
  if (!confirm("⚠️ Naozaj chcete vymazať celú databázu a zresetovať investície agentov späť na 100€?")) {
    return;
  }
  const btn = document.getElementById('btnReset');
  btn.disabled = true;
  btn.textContent = '...';
  try {
    const r = await fetch('/api/reset', { method: 'POST' });
    const data = await r.json();
    if (data.status === 'ok') {
        showToast('🗑️ ' + data.message);
        // Force full page reload to clear old charts from memory
        setTimeout(() => location.reload(), 1500);
    } else {
        showToast('❌ Chyba: ' + data.message);
        btn.disabled = false;
        btn.textContent = '✖ Reset';
    }
  } catch (e) {
    showToast('❌ Chyba pripájania');
    btn.disabled = false;
    btn.textContent = '✖ Reset';
  }
}

function showToast(msg) {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// Start
init();
