const viewNames = {
  advisor: '智能投顾',
  stock: '对话选股',
  portfolio: '持仓分析',
  kyc: 'KYC 与配置',
  rag: '知识库问答'
};

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
  toastTimer = setTimeout(() => toast.classList.remove('show'), 2800);
}

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

function escapeHTML(value) {
  return value.replace(/[&<>'"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  })[character]);
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function setStage(index, state, label) {
  const stage = stages[index];
  stage.classList.remove('active', 'done');
  stage.classList.add(state);
  stage.querySelector('.stage-state').textContent = label;
}

function renderTasks() {
  const tasks = [
    ['语义分析与指标抽取', '2 个实体 · Schema 对齐', '0.3s'],
    ['Text2SQL 与 Mock 查询', '只读 SELECT · 返回 4 行', '0.4s'],
    ['结果校验与后处理', '表格与指标摘要', '0.2s']
  ];
  taskList.innerHTML = tasks.map(([name, detail, duration]) => `
    <div class="task-item">
      <svg><use href="#i-check"/></svg>
      <div><strong>${name}</strong><small>${detail}</small></div>
      <span class="task-duration">${duration}</span>
    </div>`).join('');
  emptyTasks.hidden = true;
  taskList.hidden = false;
  taskCount.textContent = '3 TASKS';
}

function stockAnswer() {
  return `
    <h3>找到 3 只严格符合条件的 Mock 股票</h3>
    <p>我将“RSI 超卖”对齐为 <strong>RSI(14) &lt; 30</strong>，将“均线多头排列”对齐为短期、中期、长期均线依次向上。另有 1 只标的接近条件，但未纳入严格结果。</p>
    <div class="answer-metrics">
      <div class="answer-metric"><span>严格符合</span><strong>3 只</strong></div>
      <div class="answer-metric"><span>最低 RSI</span><strong>24.8</strong></div>
      <div class="answer-metric"><span>结果可信度</span><strong>已校验</strong></div>
    </div>
    <div class="answer-evidence"><strong>执行依据 · Mock SQLite</strong><p>SELECT symbol, name, rsi_14, ma_trend FROM mock_technical_indicators WHERE rsi_14 &lt; 30 AND ma_trend = 'BULLISH' LIMIT 50;</p></div>
    <p class="answer-disclaimer">以上为虚构数据与固定前端响应，仅用于展示 Agent 工作流，不构成证券推荐。</p>`;
}

function genericAnswer() {
  return `
    <h3>四阶段演示已执行完成</h3>
    <p>当前静态 Demo 只为“RSI 超卖 + 均线多头排列”内置了完整业务结果。你的问题已用于演示 Agent 状态变化，但尚未连接真实 LLM、数据库或金融模型。</p>
    <div class="answer-evidence"><strong>如何查看完整示例</strong><p>点击“新对话”，选择“对话选股”预置问题；也可以从左侧进入持仓分析、KYC 与配置或知识库问答。</p></div>
    <p class="answer-disclaimer">此处不生成未经数据支持的金融结论。</p>`;
}

function renderAnswer(query) {
  const isStockQuery = /RSI|股票|选股|筛选|均线/i.test(query);
  const answer = document.querySelector('#answer-content');
  answer.innerHTML = isStockQuery ? stockAnswer() : genericAnswer();
  document.querySelector('#answer-loading').hidden = true;
  answer.hidden = false;
  chatScroll.scrollTo({ top: chatScroll.scrollHeight, behavior: 'smooth' });
}

async function runPipeline(query) {
  const cleanQuery = query.trim();
  if (!cleanQuery) {
    showToast('请输入一个金融问题');
    queryInput.focus();
    return;
  }

  const token = ++activeRun;
  resetStages();
  sendButton.disabled = true;
  runId.textContent = `RUN-${String(Math.floor(Math.random() * 900) + 100)}`;
  runId.classList.add('running');
  chatScroll.innerHTML = `
    <div class="chat-messages">
      <div class="message user"><div class="message-body">${escapeHTML(cleanQuery)}</div></div>
      <div class="message agent">
        <div class="message-avatar"><svg><use href="#i-logo"/></svg></div>
        <div class="message-body">
          <div class="message-author">FinAgent <span>四阶段多智能体流水线</span></div>
          <div class="answer-loading" id="answer-loading"><div class="loading-dots"><i></i><i></i><i></i></div><span id="loading-copy">规划代理正在理解问题……</span></div>
          <div class="final-answer" id="answer-content" hidden></div>
        </div>
      </div>
    </div>`;
  queryInput.value = '';

  const loadingCopy = () => document.querySelector('#loading-copy');
  const steps = [
    ['规划代理正在理解问题……', '已完成', '识别为复杂查询 · 拆解 3 项任务'],
    ['执行代理正在调用工具与模型……', '已完成', '3 项任务执行成功'],
    ['验证代理正在检查证据……', '已通过', 'Schema / SQL / 结果校验通过'],
    ['融合代理正在生成最终答案……', '已完成', '答案与风险提示已生成']
  ];

  for (let index = 0; index < steps.length; index += 1) {
    if (token !== activeRun) return;
    setStage(index, 'active', '运行中');
    if (loadingCopy()) loadingCopy().textContent = steps[index][0];
    await delay(index === 1 ? 900 : 650);
    if (token !== activeRun) return;
    setStage(index, 'done', steps[index][1]);
    stages[index].querySelector('.stage-detail').textContent = steps[index][2];
    if (index === 1) renderTasks();
  }

  if (token !== activeRun) return;
  validationNote.classList.add('success');
  validationNote.querySelector('span').textContent = '验证通过 · 3 项任务证据完整 · 未触发重规划';
  runId.classList.remove('running');
  sendButton.disabled = false;
  renderAnswer(cleanQuery);
}

document.addEventListener('click', event => {
  const nav = event.target.closest('.nav-item');
  if (nav) switchView(nav.dataset.view);

  const querySuggestion = event.target.closest('[data-query]');
  if (querySuggestion) {
    switchView('advisor');
    const query = querySuggestion.dataset.query;
    queryInput.value = query;
    runPipeline(query);
  }

  const action = event.target.closest('[data-action]');
  if (action) switchView(action.dataset.action);
});

document.querySelector('#mobile-menu').addEventListener('click', () => {
  document.querySelector('#sidebar').classList.toggle('open');
});

document.querySelector('#reset-chat').addEventListener('click', resetChat);
document.querySelector('#query-form').addEventListener('submit', event => {
  event.preventDefault();
  runPipeline(queryInput.value);
});
queryInput.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    runPipeline(queryInput.value);
  }
});

document.querySelector('#run-stock').addEventListener('click', async event => {
  const input = document.querySelector('#stock-query');
  if (!input.value.trim()) {
    showToast('请输入选股条件');
    input.focus();
    return;
  }
  const button = event.currentTarget;
  button.disabled = true;
  button.textContent = '正在执行…';
  await delay(700);
  button.disabled = false;
  button.innerHTML = '运行查询<svg><use href="#i-arrow"/></svg>';
  showToast('Mock 查询完成：4 行结果，SQL 安全校验通过');
  document.querySelector('.result-card').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
});

const ocrStatus = document.querySelector('#ocr-status');
document.querySelector('#load-portfolio').addEventListener('click', () => {
  ocrStatus.innerHTML = '<span class="status-dot"></span><span>示例持仓载入完成 · Mock OCR 置信度 98.2%</span>';
  showToast('已载入 5 项虚构持仓，未执行真实 OCR');
});
document.querySelector('#choose-file').addEventListener('click', () => document.querySelector('#portfolio-file').click());
document.querySelector('#portfolio-file').addEventListener('change', event => {
  const file = event.target.files[0];
  if (!file) return;
  ocrStatus.innerHTML = `<span class="status-dot"></span><span>已选择 ${escapeHTML(file.name)} · 静态 Demo 未执行 OCR</span>`;
  showToast('图片仅保留在本地文件输入中，未上传或识别');
});
document.querySelector('#show-optimization').addEventListener('click', event => {
  const result = document.querySelector('#optimization-result');
  result.hidden = !result.hidden;
  event.currentTarget.innerHTML = `${result.hidden ? '查看' : '收起'} Mock 优化方向<svg><use href="#i-arrow"/></svg>`;
});

const kycQuestions = [
  {
    label: '问题 3 / 5 · 风险承受能力',
    title: '如果投资在一个月内下跌 10%，你更可能怎么做？',
    options: [
      ['保守', '卖出大部分，避免继续亏损'],
      ['稳健', '暂时观望，等待市场恢复'],
      ['积极', '视为机会，适当增加投入']
    ],
    apply: value => { document.querySelector('#profile-risk').textContent = value; }
  },
  {
    label: '问题 4 / 5 · 支出流向',
    title: '你目前最主要的固定支出流向是什么？',
    options: [
      ['住房支出', '房租或房贷'],
      ['家庭生活', '家庭生活与教育'],
      ['消费及其他', '消费、旅行及其他']
    ],
    apply: value => { document.querySelector('#profile-spending').textContent = value; }
  },
  {
    label: '问题 5 / 5 · 固定支出占比',
    title: '固定支出大约占你每月收入的多少？',
    options: [
      ['30% 以下', '30% 以下'],
      ['30%–60%', '30%–60%'],
      ['60% 以上', '60% 以上']
    ],
    apply: value => { document.querySelector('#profile-expense').textContent = value; }
  }
];
let kycStep = 0;

function addKycMessage(text, type) {
  const message = document.createElement('div');
  message.className = `kyc-message ${type}`;
  message.textContent = text;
  const messages = document.querySelector('#kyc-messages');
  messages.appendChild(message);
  messages.scrollTop = messages.scrollHeight;
}

function renderKycQuestion() {
  const question = kycQuestions[kycStep];
  document.querySelector('#kyc-question-label').textContent = question.label;
  document.querySelector('#kyc-question-title').textContent = question.title;
  document.querySelector('#answer-options').innerHTML = question.options.map(([value, text]) => `<button data-value="${value}">${text}</button>`).join('');
  document.querySelector('#kyc-progress-text').textContent = `${kycStep + 3} / 5`;
  document.querySelector('#kyc-progress-bar').style.width = `${(kycStep + 3) * 20}%`;
}

function completeKyc() {
  const risk = document.querySelector('#profile-risk').textContent;
  const allocations = {
    '保守': { stock: 15, fund: 45, cash: 40, color: ['#6f96b5', '#a9bdd0', '#dfe5ed'] },
    '稳健': { stock: 30, fund: 50, cash: 20, color: ['#2f66b1', '#7ca0ca', '#c2a163'] },
    '积极': { stock: 50, fund: 40, cash: 10, color: ['#2f66b1', '#6f96b5', '#c2a163'] }
  };
  const allocation = allocations[risk] || allocations['稳健'];
  document.querySelector('#kyc-progress-text').textContent = '5 / 5';
  document.querySelector('#kyc-progress-bar').style.width = '100%';
  document.querySelector('#risk-profile-badge').textContent = `${risk}型`;
  document.querySelector('#kyc-question').innerHTML = `
    <div class="kyc-complete"><span class="complete-icon"><svg><use href="#i-check"/></svg></span><h3>风险画像已完成</h3><p>已根据 5 项回答更新配置预览，结果仅为规则化 Mock 演示。</p><button class="secondary-button" id="restart-kyc">重新演示</button></div>`;
  document.querySelector('#restart-kyc').addEventListener('click', restartKyc);
  document.querySelector('#allocation-title').textContent = `${risk}型配置示例`;
  document.querySelector('#kyc-donut').style.background = `conic-gradient(${allocation.color[0]} 0 ${allocation.stock}%, ${allocation.color[1]} ${allocation.stock}% ${allocation.stock + allocation.fund}%, ${allocation.color[2]} ${allocation.stock + allocation.fund}% 100%)`;
  document.querySelector('#kyc-donut strong').textContent = risk;
  const values = [allocation.stock, allocation.fund, allocation.cash];
  document.querySelectorAll('#allocation-bars > div').forEach((row, index) => {
    row.querySelector('b').style.width = `${values[index]}%`;
    row.querySelector('strong').textContent = `${values[index]}%`;
  });
  document.querySelector('#allocation-note').textContent = `根据“${risk}”风险回答生成的固定比例示例，未调用真实组合优化模型。`;
  addKycMessage('KYC 已完成，右侧配置预览已更新。', 'agent');
}

function restartKyc() {
  kycStep = 0;
  document.querySelector('#kyc-question').innerHTML = '<span class="card-label" id="kyc-question-label"></span><h3 id="kyc-question-title"></h3><div class="answer-options" id="answer-options"></div>';
  ['#profile-risk', '#profile-spending', '#profile-expense'].forEach(selector => { document.querySelector(selector).textContent = '待回答'; });
  document.querySelector('#risk-profile-badge').textContent = '待完善';
  document.querySelector('#allocation-title').textContent = '完成 KYC 后生成';
  document.querySelector('#kyc-donut').style.background = 'conic-gradient(#dfe5ed 0 100%)';
  document.querySelector('#kyc-donut strong').textContent = '—';
  document.querySelectorAll('#allocation-bars > div').forEach(row => {
    row.querySelector('b').style.width = '0%';
    row.querySelector('strong').textContent = '—';
  });
  document.querySelector('#allocation-note').textContent = '配置比例将根据你的回答更新，仅用于演示画像如何影响模型约束。';
  addKycMessage('已重置问答，请重新回答风险承受能力。', 'agent');
  renderKycQuestion();
}

document.querySelector('#kyc-question').addEventListener('click', event => {
  const button = event.target.closest('button[data-value]');
  if (!button || !kycQuestions[kycStep]) return;
  const question = kycQuestions[kycStep];
  addKycMessage(button.textContent, 'user');
  question.apply(button.dataset.value);
  kycStep += 1;
  if (kycStep >= kycQuestions.length) {
    completeKyc();
  } else {
    renderKycQuestion();
    addKycMessage(`已记录：${button.dataset.value}。请继续下一题。`, 'agent');
  }
});

document.querySelector('#rag-form').addEventListener('submit', async event => {
  event.preventDefault();
  const input = document.querySelector('#rag-query');
  if (!input.value.trim()) {
    showToast('请输入知识库问题');
    input.focus();
    return;
  }
  const button = event.currentTarget.querySelector('button');
  button.disabled = true;
  button.textContent = '正在检索…';
  await delay(650);
  button.disabled = false;
  button.innerHTML = '检索并回答<svg><use href="#i-arrow"/></svg>';
  showToast('已展示预置 Mock 检索结果与引用，未调用真实向量库');
});
