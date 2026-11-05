const viewNames = { advisor: '智能投顾', stock: '对话选股', portfolio: '持仓分析', kyc: 'KYC 与配置', rag: '知识库问答' };
const stages = [...document.querySelectorAll('.stage')];
const chatScroll = document.querySelector('#chat-scroll');
const welcomeHTML = chatScroll.innerHTML;
const queryInput = document.querySelector('#query-input');
const sendButton = document.querySelector('.send-button');
const taskList = document.querySelector('#task-list');
const emptyTasks = document.querySelector('#empty-tasks');
const taskCount = document.querySelector('#task-count');
const runId = document.querySelector('#run-id');
const validationNote = document.querySelector('#validation-note');
let activeRun = 0;
let toastTimer;

function showToast(message) {
  const toast = document.querySelector('#toast');
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 3200);
}
function escapeHTML(value) {
  return String(value ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[c]);
}
function delay(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
async function apiRequest(path, options = {}) {
  const request = { ...options, headers: { ...(options.headers || {}) } };
  if (request.body && !(request.body instanceof FormData)) request.headers['Content-Type'] = 'application/json';
  const response = await fetch(path, request);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail || payload);
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return payload;
}
function postJSON(path, body) { return apiRequest(path, { method: 'POST', body: JSON.stringify(body) }); }
function percent(value, digits = 1, signed = false) {
  const number = Number(value || 0) * 100;
  return `${signed && number > 0 ? '+' : ''}${number.toFixed(digits)}%`;
}
function number(value, digits = 2) { return Number(value || 0).toFixed(digits); }
function switchView(name) {
  if (!viewNames[name]) return;
  document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view.id === `view-${name}`));
  document.querySelectorAll('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.view === name));
  document.querySelector('#breadcrumb-current').textContent = viewNames[name];
  document.querySelector('#sidebar').classList.remove('open');
  document.querySelector('.content-shell').scrollTop = 0;
}
function resetStages() {
  stages.forEach(stage => {
    stage.classList.remove('active', 'done');
    stage.querySelector('.stage-state').textContent = '等待';
  });
  taskList.hidden = true;
  taskList.innerHTML = '';
  emptyTasks.hidden = false;
  taskCount.textContent = '0 TASKS';
  runId.textContent = 'READY';
  runId.classList.remove('running');
  validationNote.classList.remove('success');
  validationNote.querySelector('span').textContent = '结果需通过验证后才会进入最终答案';
}
function resetChat() {
  activeRun += 1;
  chatScroll.innerHTML = welcomeHTML;
  queryInput.value = '';
  sendButton.disabled = false;
  resetStages();
}
function setStage(index, status, label, detail) {
  const stage = stages[index];
  stage.classList.remove('active', 'done');
  if (status) stage.classList.add(status);
  stage.querySelector('.stage-state').textContent = label;
  if (detail) stage.querySelector('.stage-detail').textContent = detail;
}
function renderPipelineTasks(result) {
  const results = new Map(result.task_results.map(item => [item.task_id, item]));
  taskList.innerHTML = result.plan.tasks.map(task => {
    const item = results.get(task.task_id) || {};
    return `<div class="task-item"><svg><use href="#i-check"/></svg><div><strong>${escapeHTML(task.task_id)} · ${escapeHTML(task.executor_name)}</strong><small>${escapeHTML(item.error || task.objective)}</small></div><span class="task-duration">${escapeHTML(item.status || 'pending')}</span></div>`;
  }).join('');
  emptyTasks.hidden = result.plan.tasks.length > 0;
  taskList.hidden = result.plan.tasks.length === 0;
  taskCount.textContent = `${result.plan.tasks.length} TASKS`;
}
function renderPipelineAnswer(result) {
  const answer = document.querySelector('#answer-content');
  const sources = result.final.sources.map(item => {
    const reference = String(item.reference || '');
    const content = item.kind === 'chart' && reference.startsWith('/charts/')
      ? `<a href="${escapeHTML(reference)}" target="_blank" rel="noopener">${escapeHTML(reference)}</a>`
      : escapeHTML(reference);
    return `<li>${escapeHTML(item.kind)} · ${content}</li>`;
  }).join('');
  const assumptions = result.final.assumptions.map(item => `<li>${escapeHTML(item)}</li>`).join('');
  const warnings = result.final.warnings.map(item => `<p class="answer-disclaimer">${escapeHTML(item)}</p>`).join('');
  answer.innerHTML = `<h3>${result.final.status === 'success' ? '后端执行完成' : '本次请求未生成投资结论'}</h3><p>${escapeHTML(result.final.answer)}</p><div class="answer-metrics"><div class="answer-metric"><span>执行任务</span><strong>${result.task_results.length}</strong></div><div class="answer-metric"><span>重规划</span><strong>${result.replan_count} 次</strong></div><div class="answer-metric"><span>验证状态</span><strong>${result.validation.passed ? '已通过' : '未通过'}</strong></div></div>${assumptions ? `<div class="answer-evidence"><strong>计算口径与假设</strong><ul>${assumptions}</ul></div>` : ''}${sources ? `<div class="answer-evidence"><strong>证据来源</strong><ul>${sources}</ul></div>` : ''}${warnings}`;
  document.querySelector('#answer-loading').hidden = true;
  answer.hidden = false;
  chatScroll.scrollTo({ top: chatScroll.scrollHeight, behavior: 'smooth' });
}
async function runPipeline(query) {
  const cleanQuery = query.trim();
  if (!cleanQuery) { showToast('请输入一个金融问题'); queryInput.focus(); return; }
  const token = ++activeRun;
  resetStages();
  sendButton.disabled = true;
  runId.textContent = 'RUNNING';
  runId.classList.add('running');
  chatScroll.innerHTML = `<div class="chat-messages"><div class="message user"><div class="message-body">${escapeHTML(cleanQuery)}</div></div><div class="message agent"><div class="message-avatar"><svg><use href="#i-logo"/></svg></div><div class="message-body"><div class="message-author">FinAgent <span>Python 四阶段多智能体流水线</span></div><div class="answer-loading" id="answer-loading"><div class="loading-dots"><i></i><i></i><i></i></div><span>后端正在执行规划、执行、验证与融合……</span></div><div class="final-answer" id="answer-content" hidden></div></div></div></div>`;
  queryInput.value = '';
  setStage(0, 'active', '运行中');
  try {
    const result = await postJSON('/api/pipeline', { query: cleanQuery, user_id: 'demo-user' });
    if (token !== activeRun) return;
    const details = [`${result.plan.tasks.length} 个任务 · iteration ${result.plan.iteration}`, `${result.task_results.filter(item => item.status === 'success').length}/${result.task_results.length} 个任务成功`, `${result.validation.checks.length} 项检查 · ${result.validation.passed ? '通过' : '未通过'}`, result.final.status];
    for (let index = 0; index < stages.length; index += 1) {
      setStage(index, 'done', index === 2 && !result.validation.passed ? '未通过' : '已完成', details[index]);
      if (index === 1) renderPipelineTasks(result);
      await delay(120);
    }
    runId.textContent = result.run_id;
    runId.classList.remove('running');
    validationNote.classList.toggle('success', result.validation.passed);
    validationNote.querySelector('span').textContent = `${result.validation.passed ? '验证通过' : '验证未通过'} · 重规划 ${result.replan_count} 次`;
    renderPipelineAnswer(result);
  } catch (error) {
    if (token !== activeRun) return;
    setStage(0, '', '失败', error.message);
    runId.textContent = 'ERROR';
    runId.classList.remove('running');
    document.querySelector('#answer-loading').hidden = true;
    const answer = document.querySelector('#answer-content');
    answer.hidden = false;
    answer.innerHTML = `<h3>后端请求失败</h3><p>${escapeHTML(error.message)}</p><p class="answer-disclaimer">请先运行 finagent serve，再通过 http://127.0.0.1:8000 打开页面。</p>`;
  } finally { if (token === activeRun) sendButton.disabled = false; }
}

function renderStock(result) {
  const rows = result.query_result.rows;
  document.querySelector('.entity-row').innerHTML = '<span class="muted">抽取实体</span>' + result.entities.map(item => `<span class="entity-chip">${escapeHTML(item.entity_name)}<small>${escapeHTML(item.entity_type)}</small></span>`).join('');
  document.querySelector('#stock-table-body').innerHTML = rows.map(row => `<tr><td><strong>${escapeHTML(row.name)}</strong><small>${escapeHTML(row.symbol)}</small></td><td><span class="rsi-value">${row.rsi_14 ?? '—'}</span></td><td>${escapeHTML(row.ma_trend || '—')}</td><td>¥ ${number(row.close)}</td><td>${row.dividend_yield == null ? '—' : `${number(row.dividend_yield)}%`}<button class="table-link" data-fundamental="${escapeHTML(row.symbol)}">基本面</button></td></tr>`).join('') || '<tr><td colspan="5">没有找到符合全部条件的 Mock 股票</td></tr>';
  const metrics = document.querySelectorAll('.metric-strip > div strong');
  const rsi = rows.map(row => Number(row.rsi_14)).filter(Number.isFinite);
  metrics[0].innerHTML = `${rows.length}<small>只</small>`;
  metrics[1].textContent = rsi.length ? (rsi.reduce((a, b) => a + b, 0) / rsi.length).toFixed(1) : '—';
  metrics[2].innerHTML = `${result.query_result.row_count}<small>行</small>`;
  metrics[3].textContent = rows[0]?.trade_date || '—';
  document.querySelector('.sql-card code').textContent = result.text2sql.sql;
  document.querySelector('.compact-process').innerHTML = result.dialogue_steps.map((step, index) => `<li class="done"><span>${index + 1}</span><div><strong>${escapeHTML(step)}</strong><small>${index === 1 ? `${result.semantic.aligned_entities.length} 个实体完成对齐` : 'Python 后端已执行'}</small></div></li>`).join('');
  document.querySelector('#rsi-chart').innerHTML = rows.filter(row => row.rsi_14 != null).map(row => `<div class="bar-item"><div class="bar-value">${row.rsi_14}</div><div class="bar-track"><span style="height:${Math.max(3, Math.min(100, Number(row.rsi_14)))}%"></span></div><small>${escapeHTML(String(row.name).replace('示例', ''))}</small></div>`).join('') + '<div class="threshold-line"><span>超卖阈值 30</span></div>';
}
async function runStock(silent = false) {
  const input = document.querySelector('#stock-query');
  if (!input.value.trim()) { if (!silent) showToast('请输入选股条件'); return; }
  const button = document.querySelector('#run-stock');
  document.querySelector('#fundamental-card').hidden = true;
  button.disabled = true;
  button.textContent = '正在执行…';
  try {
    const result = await postJSON('/api/database', { query: input.value.trim(), user_id: 'demo-user' });
    renderStock(result);
    if (!silent) showToast(`后端查询完成：${result.query_result.row_count} 行，SQL 安全校验通过`);
  } catch (error) {
    document.querySelector('#stock-table-body').innerHTML = `<tr><td colspan="5">${escapeHTML(error.message)}</td></tr>`;
    if (!silent) showToast(error.message);
  } finally { button.disabled = false; button.innerHTML = '运行查询<svg><use href="#i-arrow"/></svg>'; }
}

async function loadFundamental(symbol) {
  const card = document.querySelector('#fundamental-card');
  const container = document.querySelector('#fundamental-result');
  card.hidden = false;
  container.innerHTML = '<p class="fundamental-note">正在计算本地基本面报告……</p>';
  try {
    const report = await apiRequest(`/api/financial/fundamental/${encodeURIComponent(symbol)}`);
    const score = report.score;
    const dimensions = [['估值', score.valuation_score], ['质量', score.quality_score], ['技术', score.technical_score], ['股息', score.dividend_score]];
    const flags = report.risk_flags.length
      ? `<ul class="fundamental-flags">${report.risk_flags.map(flag => `<li>${escapeHTML(flag)}</li>`).join('')}</ul>`
      : '<p class="fundamental-note">未触发本地规则风险标记，不代表未来没有风险。</p>';
    container.innerHTML = `<div class="fundamental-title"><strong>${escapeHTML(report.name)} · ${escapeHTML(report.symbol)}</strong><span>${number(score.total_score)} / 100</span></div><div class="fundamental-score-grid">${dimensions.map(([label, value]) => `<div><span>${label}</span><strong>${number(value)}</strong></div>`).join('')}</div><p class="fundamental-note">${escapeHTML(report.summary)}</p>${flags}<p class="fundamental-note">${report.assumptions.map(escapeHTML).join(' ')}</p>`;
  } catch (error) {
    container.innerHTML = `<p class="fundamental-note">${escapeHTML(error.message)}</p>`;
  }
}

function renderPortfolio(result) {
  const risk = result.risk;
  document.querySelector('.risk-score-card h3').textContent = `${risk.level} · ${number(risk.score, 0)} 分`;
  document.querySelector('.risk-badge').textContent = risk.level;
  document.querySelector('.score-ring').style.background = `conic-gradient(#c2a163 0 ${Math.min(100, risk.score)}%, #e8edf3 ${Math.min(100, risk.score)}% 100%)`;
  document.querySelector('.score-ring strong').textContent = number(risk.score, 0);
  document.querySelector('.score-copy p').textContent = `年化波动 ${percent(risk.annualized_volatility)}，最大回撤 ${percent(risk.max_drawdown)}，HHI ${number(risk.hhi, 3)}。`;
  document.querySelector('.score-copy span').textContent = '由持仓市值、收益率序列与集中度实时计算';
  const colors = ['#2f66b1', '#6f96b5', '#c2a163', '#7c759f', '#9aabbc', '#d6dee8'];
  let cursor = 0;
  const segments = result.sectors.map((sector, index) => {
    const start = cursor;
    cursor += sector.weight * 100;
    return `${colors[index % colors.length]} ${start}% ${cursor}%`;
  });
  document.querySelector('.portfolio-donut').style.background = `conic-gradient(${segments.join(',')})`;
  document.querySelector('.portfolio-donut strong').textContent = result.holdings.length;
  document.querySelector('.legend').innerHTML = result.sectors.map((sector, index) => `<div><span><i class="legend-dot" style="background:${colors[index % colors.length]}"></i>${escapeHTML(sector.sector)}</span><strong>${percent(sector.weight)}</strong></div>`).join('');
  document.querySelector('.holdings-card h3').textContent = '持仓明细与收益贡献';
  document.querySelector('.holdings-card .tiny-badge').textContent = 'PYTHON MODEL · REAL CALCULATION';
  document.querySelector('.holdings-card tbody').innerHTML = result.holdings.map(item => `<tr><td><strong>${escapeHTML(item.name)}</strong><small>${escapeHTML(item.symbol)}</small></td><td><div class="weight-cell"><span>${percent(item.weight)}</span><i><b style="width:${Math.min(100, item.weight * 100)}%"></b></i></div></td><td class="${item.period_return >= 0 ? 'positive' : 'negative'}">${percent(item.period_return, 1, true)}</td><td class="${item.contribution >= 0 ? 'positive' : 'negative'}">${percent(item.contribution, 2, true)}</td><td><span class="signal ${item.signal && item.signal !== '正常' ? 'warning' : ''}">${escapeHTML(item.signal || '正常')}</span></td></tr>`).join('');
  document.querySelectorAll('.diagnosis-card .diagnosis-item').forEach(item => item.remove());
  const button = document.querySelector('#show-optimization');
  const diagnoses = result.diagnoses.length ? result.diagnoses : ['当前示例未触发集中度、波动、回撤、VaR 或跑输基准阈值；这不代表未来没有风险。'];
  diagnoses.forEach((diagnosis, index) => button.insertAdjacentHTML('beforebegin', `<div class="diagnosis-item"><span>${String(index + 1).padStart(2, '0')}</span><div><strong>模型诊断</strong><p>${escapeHTML(diagnosis)}</p></div></div>`));
  document.querySelector('#optimization-result').innerHTML = `<strong>${escapeHTML(result.optimization.method)}</strong><p>${Object.entries(result.optimization.weights).map(([symbol, weight]) => `${escapeHTML(symbol)} ${percent(weight)}`).join(' · ')}</p><p>预期持有期收益 ${percent(result.optimization.expected_return)} · 年化波动 ${percent(result.optimization.volatility)}</p><p>${result.optimization.constraints.map(escapeHTML).join('；')}</p>`;
  document.querySelector('#ocr-status').innerHTML = `<span class="status-dot"></span><span>组合收益 ${percent(result.total_return, 2, true)} · 基准 ${percent(result.benchmark_return, 2, true)} · 主动 ${percent(result.active_return, 2, true)}</span>`;
}
async function loadPortfolio(silent = false) {
  const button = document.querySelector('#load-portfolio');
  button.disabled = true;
  document.querySelector('#ocr-status').innerHTML = '<span class="status-dot"></span><span>Python 模型正在计算示例持仓……</span>';
  try {
    renderPortfolio(await apiRequest('/api/portfolio/sample'));
    if (!silent) showToast('示例持仓已完成收益、归因、风险与约束优化计算');
  } catch (error) {
    document.querySelector('#ocr-status').textContent = error.message;
    if (!silent) showToast(error.message);
  } finally { button.disabled = false; }
}
async function uploadPortfolio(file) {
  const form = new FormData();
  form.append('file', file);
  document.querySelector('#ocr-status').textContent = '正在上传本地 API 并执行 OCR……';
  try {
    renderPortfolio(await apiRequest('/api/portfolio/upload', { method: 'POST', body: form }));
    showToast('OCR 与持仓分析已完成');
  } catch (error) { document.querySelector('#ocr-status').textContent = error.message; showToast(error.message); }
}

const kycLabels = { investment_experience: '投资经验', loss_reaction: '风险承受能力', fixed_expense_destination: '主要支出流向', fixed_expense_ratio: '固定支出占比', investment_horizon: '计划投资期限' };
const kycValueLabels = {
  none: '没有投资经验', under_3_years: '3 年以内', '3_to_5_years': '3 至 5 年', over_5_years: '5 年以上', professional: '专业投资经验',
  sell_all: '全部卖出', sell_part: '卖出一部分', hold: '保持持仓', buy_small: '小幅分批买入', buy_more: '积极买入',
  basic_living: '基本生活开销', housing_loan: '住房或长期贷款', education_eldercare: '教育或赡养支出', insurance_savings: '保险或长期储蓄',
  under_20: '低于 20%', '20_to_40': '20% 至 40%', '40_to_60': '40% 至 60%', over_60: '高于 60%',
  under_1_year: '1 年以内', '1_to_3_years': '1 至 3 年', '5_to_10_years': '5 至 10 年', over_10_years: '10 年以上'
};
function kycValue(value) { return kycValueLabels[value] || value || '待回答'; }
function allocationPercent(value) { const n = Number(value || 0); return n <= 1 ? n * 100 : n; }
function renderKyc(kyc) {
  const answered = kyc.completed ? 5 : kyc.step;
  document.querySelector('#kyc-progress-text').textContent = `${answered} / 5`;
  document.querySelector('#kyc-progress-bar').style.width = `${answered * 20}%`;
  const messages = document.querySelector('#kyc-messages');
  messages.innerHTML = '<div class="kyc-message agent">你好，我会通过 5 个问题完善风险画像。回答仅保存到本地 SQLite。</div>';
  Object.entries(kyc.answers).forEach(([id, value]) => messages.insertAdjacentHTML('beforeend', `<div class="kyc-message agent">${escapeHTML(kycLabels[id] || id)}</div><div class="kyc-message user">${escapeHTML(kycValue(value))}</div>`));
  const question = document.querySelector('#kyc-question');
  if (kyc.completed) {
    question.innerHTML = `<div class="kyc-complete"><span class="complete-icon"><svg><use href="#i-check"/></svg></span><h3>${escapeHTML(kyc.risk_level)}型画像已完成</h3><p>配置比例由后端根据风险分、投资期限和支出约束计算。</p><button class="secondary-button" id="restart-kyc">重新评估</button></div>`;
  } else if (kyc.question) {
    question.innerHTML = `<span class="card-label">问题 ${kyc.step + 1} / 5 · ${escapeHTML(kycLabels[kyc.question.id] || '风险画像')}</span><h3>${escapeHTML(kyc.question.title)}</h3><div class="answer-options">${kyc.question.options.map(option => `<button data-question-id="${escapeHTML(kyc.question.id)}" data-value="${escapeHTML(option.value)}">${escapeHTML(option.label)}</button>`).join('')}</div>`;
  }
  const answer = id => kycValue(kyc.answers[id]);
  document.querySelector('.profile-list').innerHTML = `<div><dt>投资经验</dt><dd>${escapeHTML(answer('investment_experience'))}</dd></div><div><dt>风险偏好</dt><dd>${escapeHTML(kyc.risk_level || '待回答')}</dd></div><div><dt>主要支出流向</dt><dd>${escapeHTML(answer('fixed_expense_destination'))}</dd></div><div><dt>固定支出占比</dt><dd>${escapeHTML(answer('fixed_expense_ratio'))}</dd></div><div><dt>计划投资期限</dt><dd>${escapeHTML(answer('investment_horizon'))}</dd></div>`;
  document.querySelector('#risk-profile-badge').textContent = kyc.completed ? `${kyc.risk_level}型` : '评估中';
  const a = kyc.allocation || {};
  const stock = allocationPercent(a.stock ?? a.stocks ?? a.equity ?? a['股票']);
  const fund = allocationPercent(a.fund ?? a.funds ?? a.fixed_income ?? a['基金']);
  const cash = allocationPercent(a.cash ?? a['现金']);
  const complete = kyc.completed && stock + fund + cash > 0;
  document.querySelector('#allocation-title').textContent = complete ? `${kyc.risk_level}型模型配置` : '完成 KYC 后生成';
  document.querySelector('#kyc-donut').style.background = complete ? `conic-gradient(#2f66b1 0 ${stock}%, #7ca0ca ${stock}% ${stock + fund}%, #c2a163 ${stock + fund}% 100%)` : 'conic-gradient(#dfe5ed 0 100%)';
  document.querySelector('#kyc-donut strong').textContent = complete ? kyc.risk_level : '—';
  [stock, fund, cash].forEach((value, index) => {
    const row = document.querySelectorAll('#allocation-bars > div')[index];
    row.querySelector('b').style.width = `${complete ? value : 0}%`;
    row.querySelector('strong').textContent = complete ? `${value.toFixed(0)}%` : '—';
  });
  document.querySelector('#allocation-note').textContent = complete ? kyc.allocation_explanation : '回答五题后由本地后端计算配置，不使用前端固定比例。';
  const environment = kyc.market_environment || {};
  document.querySelector('#market-cycle').textContent = environment.economic_cycle || '完成 KYC 后展示虚构情景';
  document.querySelector('#market-rate').textContent = environment.market_interest_rate || '完成 KYC 后展示虚构情景';
  document.querySelector('#market-policy').textContent = environment.policies_and_regulations || '未接入实时政策资讯';
}
async function loadKyc(silent = false) {
  try {
    const current = await apiRequest('/api/kyc/status?user_id=demo-user');
    renderKyc(current.profile.kyc ? current : await postJSON('/api/kyc/start', { user_id: 'demo-user' }));
  } catch (error) { document.querySelector('#kyc-question').textContent = error.message; if (!silent) showToast(error.message); }
}
async function answerKyc(button) {
  document.querySelectorAll('#kyc-question .answer-options button').forEach(item => { item.disabled = true; });
  try { renderKyc(await postJSON('/api/kyc/answer', { user_id: 'demo-user', question_id: button.dataset.questionId, value: button.dataset.value })); }
  catch (error) { showToast(error.message); document.querySelectorAll('#kyc-question .answer-options button').forEach(item => { item.disabled = false; }); }
}

function citations(text) { return escapeHTML(text).replace(/\[(\d+)\]/g, '<sup>[$1]</sup>'); }
function renderRag(result) {
  const paragraphs = result.answer.split(/\n+/).filter(Boolean).map(text => `<p>${citations(text)}</p>`).join('');
  document.querySelector('#rag-answer').innerHTML = `<h2>${result.status === 'ok' ? '基于本地索引的检索回答' : '当前知识库证据不足'}</h2>${paragraphs}<div class="answer-callout"><svg><use href="#i-shield"/></svg><p>回答仅使用下方检索片段，知识内容为虚构金融教育材料，不构成投资建议。</p></div>`;
  document.querySelector('.tag-row').innerHTML = '<span>自动标签</span>' + result.tags.map(tag => `<span class="tag">${escapeHTML(tag)}</span>`).join('');
  document.querySelector('#view-rag .outline-badge').textContent = `${result.sources.length} 个引用来源`;
  document.querySelector('#rag-evidence-status').textContent = result.status === 'ok' ? '本地引用可追溯' : '证据不足';
  document.querySelector('.answer-meta div span').textContent = `基于 ${result.sources.length} 个真实检索片段生成`;
  const sources = document.querySelector('.sources-card');
  sources.querySelectorAll('.source-item').forEach(item => item.remove());
  result.sources.forEach((source, index) => sources.insertAdjacentHTML('beforeend', `<article class="source-item"><div><span class="source-index">[${index + 1}]</span><span class="similarity">BM25 ${number(source.score, 3)}</span></div><h4>${escapeHTML(source.title)}</h4><p>${escapeHTML(source.text)}</p><footer><span><svg><use href="#i-file"/></svg>${escapeHTML(source.source)}</span><span>第 ${escapeHTML(source.page)} 页</span></footer></article>`));
}
async function runRag(silent = false) {
  const input = document.querySelector('#rag-query');
  if (!input.value.trim()) { if (!silent) showToast('请输入知识库问题'); return; }
  const button = document.querySelector('#rag-form button');
  button.disabled = true;
  button.textContent = '正在检索…';
  try {
    const result = await postJSON('/api/rag', { query: input.value.trim(), top_k: 3, tags: [] });
    renderRag(result);
    if (!silent) showToast(`本地 BM25 检索完成：${result.sources.length} 个引用片段`);
  } catch (error) {
    document.querySelector('#rag-answer').innerHTML = `<h2>检索失败</h2><p>${escapeHTML(error.message)}</p>`;
    if (!silent) showToast(error.message);
  } finally { button.disabled = false; button.innerHTML = '检索并回答<svg><use href="#i-arrow"/></svg>'; }
}

function clearDynamicViews() {
  document.querySelector('#stock-table-body').innerHTML = '<tr><td colspan="5">正在请求 Python 后端……</td></tr>';
  document.querySelector('.sql-card code').textContent = '';
  document.querySelector('.holdings-card tbody').innerHTML = '<tr><td colspan="5">正在计算示例持仓……</td></tr>';
  document.querySelector('.risk-score-card h3').textContent = '等待后端计算';
  document.querySelector('.risk-badge').textContent = '—';
  document.querySelector('.score-ring strong').textContent = '—';
  document.querySelector('.score-copy p').textContent = '风险指标将由本地 Python 模型计算。';
  document.querySelector('.legend').innerHTML = '';
  document.querySelector('.portfolio-donut strong').textContent = '—';
  document.querySelectorAll('.diagnosis-card .diagnosis-item').forEach(item => item.remove());
  document.querySelector('#kyc-question').innerHTML = '<p>正在读取本地 KYC 状态……</p>';
  document.querySelector('#rag-answer').innerHTML = '<h2>正在检索本地知识索引</h2>';
  document.querySelectorAll('.sources-card .source-item').forEach(item => item.remove());
}
document.addEventListener('click', event => {
  const nav = event.target.closest('.nav-item');
  if (nav) switchView(nav.dataset.view);
  const suggestion = event.target.closest('[data-query]');
  if (suggestion) { switchView('advisor'); queryInput.value = suggestion.dataset.query; runPipeline(suggestion.dataset.query); }
  const action = event.target.closest('[data-action]');
  if (action) switchView(action.dataset.action);
  const fundamental = event.target.closest('[data-fundamental]');
  if (fundamental) loadFundamental(fundamental.dataset.fundamental);
});
document.querySelector('#mobile-menu').addEventListener('click', () => document.querySelector('#sidebar').classList.toggle('open'));
document.querySelector('#reset-chat').addEventListener('click', resetChat);
document.querySelector('#query-form').addEventListener('submit', event => { event.preventDefault(); runPipeline(queryInput.value); });
queryInput.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); runPipeline(queryInput.value); } });
document.querySelector('#run-stock').addEventListener('click', () => runStock());
document.querySelector('#load-portfolio').addEventListener('click', () => loadPortfolio());
document.querySelector('#choose-file').addEventListener('click', () => document.querySelector('#portfolio-file').click());
document.querySelector('#portfolio-file').addEventListener('change', event => { const file = event.target.files[0]; if (file) uploadPortfolio(file); event.target.value = ''; });
document.querySelector('#show-optimization').addEventListener('click', event => {
  const result = document.querySelector('#optimization-result');
  result.hidden = !result.hidden;
  event.currentTarget.innerHTML = `${result.hidden ? '查看' : '收起'}模型优化结果<svg><use href="#i-arrow"/></svg>`;
});
document.querySelector('#kyc-question').addEventListener('click', event => {
  const answer = event.target.closest('button[data-value]');
  if (answer) answerKyc(answer);
  if (event.target.closest('#restart-kyc')) postJSON('/api/kyc/start', { user_id: 'demo-user' }).then(renderKyc).catch(error => showToast(error.message));
});
document.querySelector('#rag-form').addEventListener('submit', event => { event.preventDefault(); runRag(); });
clearDynamicViews();
Promise.allSettled([runStock(true), loadPortfolio(true), loadKyc(true), runRag(true)]);
