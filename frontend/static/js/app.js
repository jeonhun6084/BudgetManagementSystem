const API = '';
let categoryChart = null;
let monthlyChart = null;
let currentPage = 0;
const PAGE_SIZE = 50;

// ナビゲーション
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    item.classList.add('active');
    const page = item.dataset.page;
    document.getElementById(`page-${page}`).classList.add('active');
    if (page === 'dashboard') loadDashboard();
    if (page === 'transactions') loadTransactions();
    if (page === 'salary') loadSalaryHistory();
    if (page === 'expenses') loadExpenses();
    if (page === 'settings') checkSettings();
    if (page === 'stocks') loadStocks();
  });
});

// 年セレクト初期化
function initYearSelect() {
  const yearSel = document.getElementById('dashboard-year');
  const salYear = document.getElementById('sal-year');
  const salMonth = document.getElementById('sal-month');
  const now = new Date();
  yearSel.innerHTML = '';
  for (let y = now.getFullYear(); y >= now.getFullYear() - 3; y--) {
    yearSel.innerHTML += `<option value="${y}">${y}年</option>`;
  }
  document.getElementById('dashboard-month').innerHTML += Array.from({length: 12}, (_, i) =>
    `<option value="${i + 1}">${i + 1}月</option>`
  ).join('');
  salYear.value = now.getFullYear();
  salMonth.value = now.getMonth() + 1;

  // 今月をデフォルトに
  document.getElementById('dashboard-month').value = now.getMonth() + 1;
}

// ダッシュボード
async function loadDashboard() {
  const year = document.getElementById('dashboard-year').value;
  const month = document.getElementById('dashboard-month').value;
  const params = new URLSearchParams({ year });
  if (month) params.append('month', month);

  const data = await fetchAPI(`/api/transactions/summary?${params}`);
  if (!data) return;

  document.getElementById('total-income').textContent = formatCurrency(data.total_income);
  document.getElementById('total-expense').textContent = formatCurrency(data.total_expense);
  const balance = data.total_income - data.total_expense;
  const balanceEl = document.getElementById('balance');
  balanceEl.textContent = formatCurrency(balance);
  balanceEl.style.color = balance >= 0 ? 'var(--income-color)' : 'var(--expense-color)';

  renderCategoryChart(data.category_breakdown);
  if (data.monthly_trend && data.monthly_trend.length > 0) {
    renderMonthlyChart(data.monthly_trend);
  }
}

function renderCategoryChart(breakdown) {
  const ctx = document.getElementById('category-chart').getContext('2d');
  if (categoryChart) categoryChart.destroy();
  if (!breakdown || breakdown.length === 0) return;

  const top8 = breakdown.slice(0, 8);
  categoryChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: top8.map(b => b.category),
      datasets: [{
        data: top8.map(b => b.amount),
        backgroundColor: [
          '#2563eb', '#7c3aed', '#db2777', '#dc2626',
          '#d97706', '#16a34a', '#0891b2', '#475569',
        ],
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'bottom', labels: { font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.label}: ¥${ctx.parsed.toLocaleString()}`
          }
        }
      }
    }
  });
}

function renderMonthlyChart(trend) {
  const ctx = document.getElementById('monthly-chart').getContext('2d');
  if (monthlyChart) monthlyChart.destroy();
  monthlyChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: trend.map(t => `${t.month}月`),
      datasets: [
        {
          label: '収入',
          data: trend.map(t => t.income),
          backgroundColor: '#86efac',
          borderColor: '#16a34a',
          borderWidth: 1,
        },
        {
          label: '支出',
          data: trend.map(t => t.expense),
          backgroundColor: '#fca5a5',
          borderColor: '#dc2626',
          borderWidth: 1,
        },
      ]
    },
    options: {
      responsive: true,
      scales: {
        y: {
          ticks: { callback: v => `¥${(v / 10000).toFixed(0)}万` }
        }
      },
      plugins: {
        legend: { position: 'top' },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: ¥${ctx.parsed.y.toLocaleString()}`
          }
        }
      }
    }
  });
}

// 収支明細
async function loadTransactions(page = 0) {
  currentPage = page;
  const params = new URLSearchParams({
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });
  const fromDate = document.getElementById('filter-from').value;
  const toDate = document.getElementById('filter-to').value;
  const source = document.getElementById('filter-source').value;
  const type = document.getElementById('filter-type').value;
  if (fromDate) params.append('from_date', fromDate);
  if (toDate) params.append('to_date', toDate);
  if (source) params.append('source', source);
  if (type) params.append('transaction_type', type);

  const data = await fetchAPI(`/api/transactions?${params}`);
  if (!data) return;

  const tbody = document.getElementById('transactions-body');
  tbody.innerHTML = data.items.map(t => `
    <tr>
      <td>${t.date}</td>
      <td>${escapeHtml(t.description)}</td>
      <td class="amount-${t.transaction_type}">
        ${t.transaction_type === 'income' ? '+' : '-'}¥${t.amount.toLocaleString()}
      </td>
      <td><span class="badge badge-${t.transaction_type}">${t.transaction_type === 'income' ? '収入' : '支出'}</span></td>
      <td>
        <select class="badge" onchange="updateCategory(${t.id}, this.value)" style="border:none;background:transparent;cursor:pointer">
          <option value="">${t.category || '未分類'}</option>
          ${getCategoryOptions(t.category)}
        </select>
      </td>
      <td><span class="badge badge-${t.source}">${sourceLabel(t.source)}</span></td>
      <td>${t.balance != null ? '¥' + t.balance.toLocaleString() : '-'}</td>
      <td>
        <button class="btn btn-danger btn-sm" onclick="deleteTransaction(${t.id})">削除</button>
      </td>
    </tr>
  `).join('');

  // ページネーション
  const totalPages = Math.ceil(data.total / PAGE_SIZE);
  const pag = document.getElementById('transactions-pagination');
  pag.innerHTML = '';
  for (let i = 0; i < totalPages && i < 10; i++) {
    const btn = document.createElement('button');
    btn.textContent = i + 1;
    if (i === page) btn.classList.add('active');
    btn.onclick = () => loadTransactions(i);
    pag.appendChild(btn);
  }
}

function getCategoryOptions(current) {
  const cats = ['食費', '交通費', '交通費', '光熱費', '通信費', '医療費', '買い物', '娯楽', '住居費', '保険', 'その他'];
  return cats.map(c => `<option value="${c}" ${c === current ? 'selected' : ''}>${c}</option>`).join('');
}

async function updateCategory(id, category) {
  await fetchAPI(`/api/transactions/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ category }),
  });
  showToast('カテゴリを更新しました', 'success');
}

async function deleteTransaction(id) {
  if (!confirm('この取引を削除しますか？')) return;
  const r = await fetchAPI(`/api/transactions/${id}`, { method: 'DELETE' });
  if (r) {
    showToast('削除しました');
    loadTransactions(currentPage);
  }
}

async function importCSV(type) {
  const input = document.getElementById(`${type}-csv`);
  const file = input.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);

  showLoading(true);
  try {
    const r = await fetch(`${API}/api/transactions/import/${type}-csv`, {
      method: 'POST',
      body: formData,
    });
    const data = await r.json();
    showToast(data.message, r.ok ? 'success' : 'error');
    if (r.ok) loadTransactions();
  } catch (e) {
    showToast('インポートエラー: ' + e.message, 'error');
  } finally {
    showLoading(false);
    input.value = '';
  }
}

// 給与計算
async function calculateSalary(save) {
  const payload = {
    year: parseInt(document.getElementById('sal-year').value),
    month: parseInt(document.getElementById('sal-month').value),
    base_salary: parseFloat(document.getElementById('sal-base').value) || 0,
    work_hours: parseFloat(document.getElementById('sal-hours').value) || 160,
    overtime_hours_125: parseFloat(document.getElementById('sal-ot125').value) || 0,
    overtime_hours_135: parseFloat(document.getElementById('sal-ot135').value) || 0,
    holiday_work_hours: parseFloat(document.getElementById('sal-holiday').value) || 0,
    commute_allowance: parseFloat(document.getElementById('sal-commute').value) || 0,
    other_allowances: parseFloat(document.getElementById('sal-other').value) || 0,
    resident_tax_monthly: parseFloat(document.getElementById('sal-resident').value) || 0,
    dependents: parseInt(document.getElementById('sal-dependents').value) || 0,
    save,
  };

  const data = await fetchAPI('/api/salary/calculate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!data) return;

  const result = document.getElementById('salary-result');
  result.style.display = 'block';

  const b = data.breakdown;
  const d = data.deductions;
  document.getElementById('r-base').textContent = formatCurrency(b.base_salary);
  document.getElementById('r-overtime').textContent = formatCurrency(b.overtime_pay || 0);
  document.getElementById('r-commute').textContent = formatCurrency(b.commute_allowance);
  document.getElementById('r-other').textContent = formatCurrency(b.other_allowances);
  document.getElementById('r-gross').textContent = formatCurrency(data.gross_salary);
  document.getElementById('r-health').textContent = formatCurrency(d.health_insurance);
  document.getElementById('r-pension').textContent = formatCurrency(d.pension);
  document.getElementById('r-employment').textContent = formatCurrency(d.employment_insurance);
  document.getElementById('r-income-tax').textContent = formatCurrency(d.income_tax);
  document.getElementById('r-resident-tax').textContent = formatCurrency(d.resident_tax);
  document.getElementById('r-total-deductions').textContent = formatCurrency(data.total_deductions);
  document.getElementById('r-net').textContent = formatCurrency(data.net_salary);

  const hi = data.hourly_info;
  document.getElementById('r-hourly-info').textContent =
    `時給: ¥${hi.hourly_rate.toFixed(0)} / 25%割増: ¥${hi.overtime_rate_125.toFixed(0)} / 35%割増: ¥${hi.overtime_rate_135.toFixed(0)}`;

  if (save) {
    showToast('給与記録を保存しました', 'success');
    loadSalaryHistory();
  }
}

async function loadSalaryHistory() {
  const data = await fetchAPI('/api/salary/records');
  if (!data) return;

  const tbody = document.getElementById('salary-history-body');
  tbody.innerHTML = data.map(r => `
    <tr>
      <td>${r.year}年${r.month}月</td>
      <td>${formatCurrency(r.base_salary)}</td>
      <td>${(r.overtime_hours_125 || 0) + (r.overtime_hours_135 || 0)}h</td>
      <td>${formatCurrency(r.gross_salary)}</td>
      <td class="amount-expense">${formatCurrency(r.total_deductions)}</td>
      <td class="amount-income">${formatCurrency(r.net_salary)}</td>
      <td>
        <button class="btn btn-danger btn-sm" onclick="deleteSalaryRecord(${r.id})">削除</button>
      </td>
    </tr>
  `).join('') || '<tr><td colspan="7" style="text-align:center;color:var(--text-muted)">記録がありません</td></tr>';
}

async function deleteSalaryRecord(id) {
  if (!confirm('この記録を削除しますか？')) return;
  const r = await fetchAPI(`/api/salary/records/${id}`, { method: 'DELETE' });
  if (r) {
    showToast('削除しました');
    loadSalaryHistory();
  }
}

// 経費申請
async function createExpense() {
  const payload = {
    date: document.getElementById('exp-date').value,
    title: document.getElementById('exp-title').value,
    category: document.getElementById('exp-category').value,
    amount: parseFloat(document.getElementById('exp-amount').value) || 0,
    description: document.getElementById('exp-description').value,
    submit_to_rakuraku: document.getElementById('exp-submit-rakuraku').checked,
  };

  if (!payload.date || !payload.title || !payload.amount) {
    showToast('必須項目を入力してください', 'error');
    return;
  }

  const data = await fetchAPI('/api/expenses', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (data) {
    showToast(data.message, 'success');
    loadExpenses();
    document.getElementById('exp-title').value = '';
    document.getElementById('exp-amount').value = '';
    document.getElementById('exp-description').value = '';
  }
}

async function loadExpenses() {
  const data = await fetchAPI('/api/expenses');
  if (!data) return;

  const tbody = document.getElementById('expenses-body');
  tbody.innerHTML = data.map(e => `
    <tr>
      <td>${e.date}</td>
      <td>${escapeHtml(e.title)}</td>
      <td>${e.category || '-'}</td>
      <td class="amount-expense">¥${e.amount.toLocaleString()}</td>
      <td>
        <span class="badge ${e.rakuraku_submitted ? 'badge-submitted' : 'badge-pending'}">
          ${e.rakuraku_submitted ? '送信済' : '未送信'}
        </span>
        ${!e.rakuraku_submitted ? `<button class="btn btn-secondary btn-sm" onclick="submitToRakuraku(${e.id})">送信</button>` : ''}
      </td>
      <td>
        <button class="btn btn-danger btn-sm" onclick="deleteExpense(${e.id})">削除</button>
      </td>
    </tr>
  `).join('') || '<tr><td colspan="6" style="text-align:center;color:var(--text-muted)">申請がありません</td></tr>';
}

async function submitToRakuraku(id) {
  const r = await fetchAPI(`/api/expenses/${id}/submit-rakuraku`, { method: 'POST' });
  if (r) showToast(r.message, 'success');
}

async function deleteExpense(id) {
  if (!confirm('この申請を削除しますか？')) return;
  const r = await fetchAPI(`/api/expenses/${id}`, { method: 'DELETE' });
  if (r) {
    showToast('削除しました');
    loadExpenses();
  }
}

// 設定確認
function checkSettings() {
  // 実際の設定状態はバックエンドで確認するが、ここでは表示のみ
  document.getElementById('smbc-status').textContent = '設定済みかどうかは.envファイルを確認してください';
}

async function triggerScraping() {
  showToast('スクレイピングを開始します。ブラウザが起動します。', 'success');
}

// ユーティリティ
async function fetchAPI(url, options = {}) {
  showLoading(true);
  try {
    const response = await fetch(API + url, options);
    const data = await response.json();
    if (!response.ok) {
      showToast(data.detail || 'エラーが発生しました', 'error');
      return null;
    }
    return data;
  } catch (e) {
    showToast('通信エラー: ' + e.message, 'error');
    return null;
  } finally {
    showLoading(false);
  }
}

function formatCurrency(amount) {
  if (amount === null || amount === undefined) return '¥0';
  return '¥' + Math.round(amount).toLocaleString();
}

function sourceLabel(source) {
  return { smbc: '住友銀行', vpass: 'Vpass', manual: '手動' }[source] || source;
}

function escapeHtml(text) {
  const d = document.createElement('div');
  d.textContent = text;
  return d.innerHTML;
}

function showToast(message, type = '') {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = `toast show ${type}`;
  setTimeout(() => toast.classList.remove('show'), 3000);
}

function showLoading(show) {
  document.getElementById('loading').style.display = show ? 'block' : 'none';
}

// ===== 株式管理 =====
const MARKET_LABELS = { JP: '日本株', US: '米国株', KS: 'KOSPI', KQ: 'KOSDAQ' };

function switchStockTab(tab) {
  document.querySelectorAll('.stock-tab-btn').forEach((b, i) => {
    const tabs = ['portfolio', 'watchlist', 'ai'];
    b.classList.toggle('active', tabs[i] === tab);
  });
  document.querySelectorAll('.stock-tab-content').forEach(el => el.classList.remove('active'));
  document.getElementById(`stock-tab-${tab}`).classList.add('active');
}

function loadStocks() {
  loadHoldings();
  loadWatchlist();
}

async function loadHoldings() {
  const data = await fetchAPI('/api/stocks/holdings');
  if (!data) return;
  const tbody = document.getElementById('holdings-body');
  if (!data.items.length) {
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--text-muted)">保有銘柄がありません</td></tr>';
    document.getElementById('portfolio-summary').style.display = 'none';
    return;
  }

  let totalJPY = 0, costJPY = 0, totalUSD = 0;
  tbody.innerHTML = data.items.map(h => {
    if (h.currency === 'JPY') { totalJPY += h.market_value; costJPY += h.cost_basis; }
    if (h.currency === 'USD') totalUSD += h.market_value;
    const chgCls = h.change_pct >= 0 ? 'chg-pos' : 'chg-neg';
    const plCls = h.pl >= 0 ? 'pl-pos' : 'pl-neg';
    const chgSign = h.change_pct >= 0 ? '+' : '';
    const plSign = h.pl >= 0 ? '+' : '';
    const cur = currencySymbol(h.currency);
    return `<tr>
      <td><strong>${escapeHtml(h.name || h.ticker)}</strong><br><small style="color:var(--text-muted)">${h.ticker}</small></td>
      <td>${MARKET_LABELS[h.market] || h.market}</td>
      <td>${h.quantity.toLocaleString()}</td>
      <td>${cur}${h.avg_buy_price.toLocaleString(undefined, {minimumFractionDigits:0,maximumFractionDigits:2})}</td>
      <td>${cur}${(h.current_price||0).toLocaleString(undefined, {minimumFractionDigits:0,maximumFractionDigits:2})}</td>
      <td class="${chgCls}">${chgSign}${h.change_pct.toFixed(2)}%</td>
      <td>${cur}${Math.round(h.market_value).toLocaleString()}</td>
      <td class="${plCls}">${plSign}${cur}${Math.round(Math.abs(h.pl)).toLocaleString()}</td>
      <td class="${plCls}">${plSign}${h.pl_pct.toFixed(2)}%</td>
      <td><button class="btn btn-danger btn-sm" onclick="deleteHolding(${h.id})">削除</button></td>
    </tr>`;
  }).join('');

  const sumEl = document.getElementById('portfolio-summary');
  sumEl.style.display = 'grid';
  document.getElementById('port-value-jpy').textContent = '¥' + Math.round(totalJPY).toLocaleString();
  document.getElementById('port-value-usd').textContent = '$' + Math.round(totalUSD).toLocaleString();
  const plJPY = totalJPY - costJPY;
  const plEl = document.getElementById('port-pl-jpy');
  plEl.textContent = (plJPY >= 0 ? '+¥' : '-¥') + Math.round(Math.abs(plJPY)).toLocaleString();
  plEl.style.color = plJPY >= 0 ? 'var(--income-color)' : 'var(--expense-color)';
}

async function addHolding() {
  const ticker = document.getElementById('h-ticker').value.trim();
  const market = document.getElementById('h-market').value;
  const qty = parseFloat(document.getElementById('h-qty').value);
  const price = parseFloat(document.getElementById('h-price').value);
  if (!ticker || isNaN(qty) || isNaN(price)) { showToast('全項目を入力してください', 'error'); return; }
  const r = await fetchAPI('/api/stocks/holdings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker, market, quantity: qty, avg_buy_price: price })
  });
  if (r) {
    showToast(r.message || '追加しました', 'success');
    document.getElementById('h-ticker').value = '';
    document.getElementById('h-qty').value = '';
    document.getElementById('h-price').value = '';
    loadHoldings();
  }
}

async function deleteHolding(id) {
  if (!confirm('削除しますか？')) return;
  const r = await fetchAPI(`/api/stocks/holdings/${id}`, { method: 'DELETE' });
  if (r) { showToast('削除しました'); loadHoldings(); }
}

async function loadWatchlist() {
  const data = await fetchAPI('/api/stocks/watchlist');
  if (!data) return;
  const tbody = document.getElementById('watchlist-body');
  if (!data.items.length) {
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--text-muted)">ウォッチリストが空です</td></tr>';
    return;
  }
  tbody.innerHTML = data.items.map(w => {
    const chgCls = w.change_pct >= 0 ? 'chg-pos' : 'chg-neg';
    const chgSign = w.change_pct >= 0 ? '+' : '';
    const cur = currencySymbol(w.currency);
    const mcap = w.market_cap ? formatLargeNum(w.market_cap, w.currency) : 'N/A';
    const per = w.pe_ratio ? w.pe_ratio.toFixed(1) : 'N/A';
    const pbr = w.pbr ? w.pbr.toFixed(2) : 'N/A';
    const div = w.dividend_yield ? (w.dividend_yield * 100).toFixed(2) + '%' : 'N/A';
    const hi = w.week52_high ? cur + w.week52_high.toLocaleString(undefined,{maximumFractionDigits:0}) : 'N/A';
    const lo = w.week52_low ? cur + w.week52_low.toLocaleString(undefined,{maximumFractionDigits:0}) : 'N/A';
    return `<tr>
      <td><strong>${escapeHtml(w.name || w.ticker)}</strong><br><small style="color:var(--text-muted)">${w.ticker}</small></td>
      <td>${MARKET_LABELS[w.market] || w.market}</td>
      <td>${cur}${(w.current_price||0).toLocaleString(undefined,{maximumFractionDigits:2})}</td>
      <td class="${chgCls}">${chgSign}${w.change_pct.toFixed(2)}%</td>
      <td>${mcap}</td>
      <td>${per}</td>
      <td>${pbr}</td>
      <td>${div}</td>
      <td style="white-space:nowrap">${hi} / ${lo}</td>
      <td>
        <button class="btn btn-secondary btn-sm" onclick="watchToAI('${w.ticker}','${w.market}')">AI分析</button>
        <button class="btn btn-danger btn-sm" onclick="deleteWatchlistItem(${w.id})">削除</button>
      </td>
    </tr>`;
  }).join('');
}

async function addWatchlistItem() {
  const ticker = document.getElementById('w-ticker').value.trim();
  const market = document.getElementById('w-market').value;
  if (!ticker) { showToast('ティッカーを入力してください', 'error'); return; }
  const r = await fetchAPI('/api/stocks/watchlist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker, market })
  });
  if (r) {
    showToast(r.message || '追加しました', 'success');
    document.getElementById('w-ticker').value = '';
    loadWatchlist();
  }
}

async function deleteWatchlistItem(id) {
  if (!confirm('削除しますか？')) return;
  const r = await fetchAPI(`/api/stocks/watchlist/${id}`, { method: 'DELETE' });
  if (r) { showToast('削除しました'); loadWatchlist(); }
}

function watchToAI(ticker, market) {
  switchStockTab('ai');
  document.getElementById('ai-ticker').value = ticker;
  document.getElementById('ai-market').value = market;
  analyzeStock();
}

async function analyzeStock() {
  const ticker = document.getElementById('ai-ticker').value.trim();
  const market = document.getElementById('ai-market').value;
  if (!ticker) { showToast('ティッカーを入力してください', 'error'); return; }
  const resultEl = document.getElementById('ai-result');
  resultEl.style.display = 'block';
  resultEl.innerHTML = '<p style="color:var(--text-muted)">Claudeが分析中... しばらくお待ちください。</p>';

  const data = await fetchAPI('/api/stocks/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker, market })
  });
  if (!data) { resultEl.style.display = 'none'; return; }

  const info = data.stock_info;
  const cur = currencySymbol(info.currency);
  const chgCls = (info.change_pct || 0) >= 0 ? 'chg-pos' : 'chg-neg';
  const chgSign = (info.change_pct || 0) >= 0 ? '+' : '';
  resultEl.innerHTML = `
    <div class="ai-stock-header">
      <div>
        <strong style="font-size:1.1rem">${escapeHtml(info.name || ticker)}</strong>
        <small style="color:var(--text-muted); margin-left:8px">${ticker} · ${MARKET_LABELS[market]}</small>
      </div>
      <div class="price">${cur}${(info.price||0).toLocaleString(undefined,{maximumFractionDigits:2})}</div>
      <div class="${chgCls}">${chgSign}${(info.change_pct||0).toFixed(2)}%</div>
    </div>
    <div>${marked.parse(data.analysis)}</div>`;
}

function currencySymbol(currency) {
  return { JPY: '¥', USD: '$', KRW: '₩', EUR: '€' }[currency] || '';
}

function formatLargeNum(n, currency) {
  const sym = currencySymbol(currency);
  if (currency === 'JPY' || currency === 'KRW') {
    if (n >= 1e12) return sym + (n / 1e12).toFixed(1) + '兆';
    if (n >= 1e8) return sym + (n / 1e8).toFixed(1) + '億';
    return sym + n.toLocaleString();
  }
  if (n >= 1e12) return sym + (n / 1e12).toFixed(2) + 'T';
  if (n >= 1e9) return sym + (n / 1e9).toFixed(2) + 'B';
  if (n >= 1e6) return sym + (n / 1e6).toFixed(2) + 'M';
  return sym + n.toLocaleString();
}

// 初期化
initYearSelect();
loadDashboard();
// 今日の日付をデフォルトに
document.getElementById('exp-date').value = new Date().toISOString().slice(0, 10);
