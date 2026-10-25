'use strict';

const $ = (selector, root = document) => root.querySelector(selector);
const escapeText = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const number = value => value === null || value === undefined ? '未知' : Number.isFinite(Number(value)) ? new Intl.NumberFormat('zh-CN', {maximumFractionDigits:3}).format(Number(value)) : escapeText(value);
const money = value => value === null || value === undefined ? '费用未知' : '$' + Number(value).toFixed(5);
const isActive = run => ['queued','running'].includes(run?.status);
const statusNames = {queued:'排队中',running:'运行中',completed:'已完成',partial:'部分完成',failed:'运行失败',interrupted:'已中断',stopped:'已停止'};
const sourceNames = {historical:'历史导入',imported:'历史导入',historical_import:'历史导入',live:'本平台运行',platform:'本平台运行',new:'本平台运行',offline:'离线核验'};
const typeNames = {cross_layer_live:'真实 API · 跨层采集',input_audit:'离线 · 输入与工件核验',semantic_diagnosis:'语义诊断'};
const inputNames = {controlled_recipe:'受控实验场景脚本',public_normalized:'公开数据 · 本地归一化输入',synthetic_fixture:'合成测试输入',public_derived_replay:'公开样本派生的冻结任务',historical_unregistered:'历史输入 · 未登记'};
const checkNames = {input:'输入文件',collector:'采集器配方',budget_files:'本次调用范围',wsl:'WSL 环境',credential:'API 凭据',compatibility:'运行兼容性',single_live_run:'运行状态'};
const state = {runs:[],datasets:[],types:[],detail:null,route:null,connected:false,preflight:null,preflightId:null,preflightLoading:false,launching:false,form:{name:'',type:'',dataset:'',consent:false},polling:false,search:'',statusFilter:'all',db:0,table:'',tableRequest:0,detailRequest:0,sourceRequest:0};

function tone(value) {
  const text = String(value ?? '').toLowerCase();
  if (/^(completed|passed|pass|confirmed|success|successful|accepted|ready|available|verified|ok|true|exact_match|linked)$/.test(text)) return 'good';
  if (/running|queued|pending|loading/.test(text)) return 'live';
  if (/fail|error|blocked|false|mismatch/.test(text)) return 'bad';
  return 'warn';
}
function badge(status, label) {return `<span class="status ${tone(status)}"><span class="status-dot ${tone(status)}"></span>${escapeText(label ?? statusNames[status] ?? status ?? '未知')}</span>`;}
function date(value, compact = false) {
  if (!value) return '时间未记录';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return escapeText(value);
  return new Intl.DateTimeFormat('zh-CN', compact ? {month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false} : {year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(parsed);
}
function sourceName(run) {return sourceNames[run.source_kind] ?? (String(run.source_kind).includes('histor') || String(run.source_kind).includes('import') ? '历史导入' : escapeText(run.source_kind || '本地记录'));}
function safeUrl(value) {return typeof value === 'string' && value.startsWith('/api/') && !value.startsWith('//') ? escapeText(value) : '';}
function fileLink(url, label, css = 'inline-link') {const safe = safeUrl(url); return safe ? `<a class="${css}" href="${safe}" target="_blank" rel="noopener noreferrer">${escapeText(label)} <span aria-hidden="true">↗</span></a>` : `<span class="muted">${escapeText(label)} · 暂无文件</span>`;}
function artifactByName(detail,name) {return (detail.artifacts || []).find(item=>item.name===name || item.name?.endsWith('/'+name));}
function empty(title, description, action = '') {return `<div class="empty"><span class="empty-icon" aria-hidden="true">◇</span><h3>${escapeText(title)}</h3><p>${escapeText(description)}</p>${action}</div>`;}
function toast(message) {const node = $('#toast');node.textContent = message;node.classList.add('visible');clearTimeout(toast.timer);toast.timer = setTimeout(() => node.classList.remove('visible'), 5000);}
async function api(path, payload) {
  const response = await fetch(path, payload === undefined ? {cache:'no-store'} : {method:'POST',headers:{'Content-Type':'application/json','X-Observatory-Control':'1'},body:JSON.stringify(payload)});
  let result;
  try {result = await response.json();} catch {throw new Error(`服务返回了无效响应（HTTP ${response.status}）。请使用新版启动脚本打开页面。`);}
  if (!response.ok) throw new Error(result.error || `请求失败：HTTP ${response.status}`);
  return result;
}
function setConnection(ok, message) {
  state.connected = ok;
  $('#connection-dot').className = `connection-dot ${ok ? 'connected' : 'offline'}`;
  $('#connection-label').textContent = message || (ok ? '本地服务已连接 · v2' : '本地服务未连接');
}
function renderSidebar() {
  $('#run-count').textContent = state.runs.length;
  $('#nav-runs').classList.toggle('active', state.route?.view === 'runs');
  $('#nav-new').classList.toggle('active', state.route?.view === 'new');
  $('#recent-runs').innerHTML = state.runs.slice(0, 12).map(run => `<a class="recent-run ${state.route?.id === run.id ? 'active' : ''}" href="#run/${encodeURIComponent(run.id)}/overview" ${state.route?.id === run.id ? 'aria-current="page"' : ''}><span class="status-dot ${tone(run.status)}"></span><span><strong>${escapeText(run.name || run.id)}</strong><small>${date(run.created_at,true)} · ${escapeText(statusNames[run.status] || run.status)}</small></span></a>`).join('') || '<p class="sidebar-muted">还没有实验。创建一次运行开始记录。</p>';
  const active = state.runs.some(isActive);
  $('#live-indicator').classList.toggle('is-live',active);
  $('#live-indicator').innerHTML = `<span></span> ${active ? '运行中 · 每 2 秒更新' : '仅本地'}`;
}
function route() {
  const parts = location.hash.slice(1).split('/');
  if (parts[0] === 'new') return {view:'new'};
  if (parts[0] === 'run' && parts[1]) {let id;try {id = decodeURIComponent(parts[1]);} catch {id=parts[1];}return {view:'run',id,tab:['overview','traces','data','files'].includes(parts[2]) ? parts[2] : 'overview'};}
  return {view:'runs'};
}
async function navigate() {
  state.route = route();renderSidebar();
  $('#breadcrumb-current').textContent = state.route.view === 'new' ? '新建实验' : state.route.view === 'run' ? '运行详情' : '所有运行';
  if (state.route.view === 'new') {renderNew();return;}
  if (state.route.view === 'runs') {renderRuns();return;}
  const id = state.route.id;
  if (state.detail?.id === id) renderRun();
  else $('#main').innerHTML = '<div class="initial-loading"><span class="spinner"></span><p>正在读取这次运行的证据…</p></div>';
  await loadDetail(id);
}
async function loadDetail(id, quiet = false) {
  const request = ++state.detailRequest;
  try {
    const detail = await api(`/api/runs/${encodeURIComponent(id)}`);
    if (request !== state.detailRequest || state.route?.id !== id) return;
    if (quiet && state.detail?.id===id && JSON.stringify(state.detail)===JSON.stringify(detail)) return;
    const changed = state.detail?.id !== id;
    state.detail = detail;
    if (changed) {state.db=0;state.table='';}
    renderRun(quiet);
  } catch (error) {
    if (request !== state.detailRequest || state.route?.id !== id) return;
    if (quiet && state.detail?.id === id) {toast(error.message);return;}
    $('#main').innerHTML = `<div class="panel page-error">${empty('无法读取这次运行',error.message,'<a class="button" href="#runs">返回所有运行</a>')}</div>`;
  }
}
function renderRuns() {
  $('#main').innerHTML = `<div class="page-heading"><div><div class="eyebrow">EXPERIMENT HISTORY</div><h1>所有实验运行</h1><p>每次实验保留独立结果，可随时打开、追溯与重复运行。</p></div><a class="button primary" href="#new"><span aria-hidden="true">＋</span> 新建实验</a></div><section class="panel"><div class="toolbar"><label class="search-field"><span aria-hidden="true">⌕</span><input id="run-search" type="text" value="${escapeText(state.search)}" placeholder="搜索名称、运行 ID 或数据集" aria-label="搜索运行"></label><select id="status-filter" aria-label="按运行状态筛选"><option value="all">全部状态</option>${Object.entries(statusNames).map(([id,name])=>`<option value="${id}" ${state.statusFilter===id?'selected':''}>${name}</option>`).join('')}</select></div><div id="run-list"></div></section><div class="note">同名实验可以重复启动。新的运行会生成独立 ID，并保存自己的数据库、调用证据与分析报告。</div>`;
  renderRunList();
  $('#run-search').addEventListener('input', event => {state.search=event.target.value;renderRunList();});
  $('#status-filter').addEventListener('change',event=>{state.statusFilter=event.target.value;renderRunList();});
}
function renderRunList() {
  const node = $('#run-list');if (!node) return;
  const filter = state.search.toLocaleLowerCase();
  const runs = state.runs.filter(run => (state.statusFilter==='all'||run.status===state.statusFilter) && [run.name,run.id,run.dataset_name,run.dataset_id].join(' ').toLocaleLowerCase().includes(filter));
  node.innerHTML = runs.length ? `<div class="table-wrap"><table class="run-table"><thead><tr><th>实验 / 运行 ID</th><th>输入数据集</th><th>状态</th><th class="date-column">启动时间</th><th class="source-column">来源</th><th></th></tr></thead><tbody>${runs.map(run=>`<tr><td><a href="#run/${encodeURIComponent(run.id)}/overview">${escapeText(run.name || run.id)}</a><div class="subline mono">${escapeText(run.id)}</div></td><td><span class="dataset-name">${escapeText(run.dataset_name || run.dataset_id || '未登记')}</span></td><td>${badge(run.status)}</td><td class="date-column muted">${date(run.created_at,true)}</td><td class="source-column"><span class="source-tag">${sourceName(run)}</span></td><td><a href="#run/${encodeURIComponent(run.id)}/overview" aria-label="查看 ${escapeText(run.name || run.id)}">→</a></td></tr>`).join('')}</tbody></table></div><p class="table-meta section-space">共 ${runs.length} 次运行${filter?' · 已筛选':''}</p>` : empty('没有符合条件的运行', state.runs.length ? '调整搜索或状态筛选后再试。' : '选择实验类型与真实输入，启动第一条实验记录。', state.runs.length?'':'<a class="button primary" href="#new">创建实验</a>');
}
function runHeader(detail) {
  const isHistorical = /histor|import/.test(detail.source_kind || '');
  return `<div class="run-heading"><div class="page-heading"><div><div class="eyebrow">${isHistorical ? 'HISTORICAL RUN' : 'EXPERIMENT RUN'}</div><div class="run-title-row"><h1>${escapeText(detail.name || detail.id)}</h1>${badge(detail.status)}</div><div class="run-context"><span>运行 <code>${escapeText(detail.id)}</code></span><span>数据集 <strong>${escapeText(detail.dataset_name || detail.dataset_id || '未登记')}</strong></span><span>${date(detail.created_at)}</span></div></div><div class="actions">${isActive(detail)?'<button class="button danger" id="stop-run">停止运行</button>':''}<button class="button" id="refresh-run" title="重新读取本次运行的工件">↻ 刷新</button><button class="button primary" id="repeat-run">＋ 再运行一次</button></div></div><div class="run-source"><span><strong>${sourceName(detail)}</strong> · 当前所有图表与证据仅对应 <code>${escapeText(detail.id)}</code></span><span>${isActive(detail) ? '自动更新中 · 2 秒' : detail.finished_at ? '结束于 '+date(detail.finished_at,true) : '独立保留原始工件'}</span></div></div><nav class="tabs" aria-label="本次运行内容">${[['overview','总览与证据'],['traces','Trace 时间线'],['data','数据与 SQLite'],['files','图表与文件']].map(([tab,label])=>`<a href="#run/${encodeURIComponent(detail.id)}/${tab}" class="${state.route.tab===tab?'active':''}" ${state.route.tab===tab?'aria-current="page"':''}>${label}</a>`).join('')}</nav>`;
}
function renderRun(quiet = false) {
  const detail = state.detail;
  if (!detail || state.route?.id!==detail.id) return;
  // Keep a focused table control or expanded trace intact during background polling.
  if (quiet && state.route.tab==='data' && document.activeElement?.closest('.database-controls')) return;
  const tab = state.route.tab;
  $('#main').innerHTML = runHeader(detail) + (tab==='traces'?renderTraces(detail):tab==='data'?renderData(detail):tab==='files'?renderFiles(detail):renderOverview(detail));
  $('#refresh-run').addEventListener('click',()=>loadDetail(detail.id));
  $('#repeat-run').addEventListener('click',()=>{
    const dataset = state.datasets.find(item=>item.id===detail.dataset_id);
    state.form={name:detail.name || dataset?.name || '',type:dataset?.experiment_type || 'cross_layer_live',dataset:detail.dataset_id || '',consent:false};state.preflight=null;state.preflightId=null;location.hash='new';
  });
  $('#stop-run')?.addEventListener('click',async event=>{
    event.currentTarget.disabled=true;
    try {await api(`/api/runs/${encodeURIComponent(detail.id)}/stop`,{});toast('已发送停止请求，正在保存运行记录。');await loadDetail(detail.id);}catch(error){toast(error.message);event.currentTarget.disabled=false;}
  });
  if (tab==='data') bindData(detail);
  $('#show-dataset-source')?.addEventListener('click',()=>loadDatasetSource(detail.dataset));
  document.querySelectorAll('.open-db-proof').forEach(button=>button.addEventListener('click',()=>{
    state.db=Number(button.dataset.db || 0);state.table=button.dataset.table || 'tool_calls';location.hash=`run/${encodeURIComponent(detail.id)}/data`;
  }));
}
function apiCard(detail) {
  const evidence = detail.api || {};
  const source = artifactByName(detail,'capture-summary.json');
  const confirmed = ['confirmed','verified','success','successful'].includes(evidence.status);
  const offline = evidence.status==='not_required';
  const absent = evidence.sessions == null;
  return `<article class="evidence-card ${confirmed?'good':evidence.status==='failed'?'bad':offline?'':'warn'}"><div class="label">01 / 真实 API 证据 ${badge(evidence.status,confirmed?'已确认':offline?'无需 API':evidence.status==='failed'?'请求失败':'待核验')}</div><h2>${escapeText(evidence.label || (confirmed ? '真实调用已确认' : '尚无可确认的调用摘要'))}</h2><div class="metric">${offline?'本地核验':absent ? '未知' : number(evidence.successful_sessions)}${offline||absent?'':`<small>/ ${number(evidence.sessions)} 会话成功</small>`}</div><p>${escapeText(offline?'此类型仅核验本地输入与工件，不执行真实 API 任务。':evidence.scope || '依据本次运行的调用摘要与用量记录。会话数量不等于 HTTP 请求数量。')}</p><div class="card-bottom"><span>${money(evidence.cost_usd)}</span><span>${offline?'离线执行':`HTTP 2xx 记录 ${number(evidence.http_successes)}${evidence.http_errors?` · 错误 ${number(evidence.http_errors)}`:''}`}</span></div>${!offline?`<p class="card-source">模型：${escapeText((evidence.models || []).map(item=>typeof item==='string'?item:item.model || item.name || '').filter(Boolean).join(' · ') || '未记录')} ${source?fileLink(source.url,'调用摘要'):''}</p>`:''}</article>`;
}
function correlationCard(detail) {
  const evidence = detail.correlation || {};
  const source = artifactByName(detail,'real-alignment-comparison.json');
  const modes = evidence.modes || {};
  const preferred = modes['session-and-tool'] || modes['shared-tool-id'];
  const accepted = preferred?.accepted;
  const known = accepted !== null && accepted !== undefined;
  const good = known && Number(accepted)>0;
  return `<article class="evidence-card ${good?'good':'warn'}"><div class="label">02 / 跨层关联 ${badge(good?'accepted':'unknown',good?'有匹配证据':'待核验')}</div><h2>${escapeText(evidence.label || '应用工具 ↔ 系统工具')}</h2><div class="metric">${number(accepted)}${known?`<small>/ ${number(evidence.native_tools)} 工具匹配</small>`:''}</div><p>${escapeText(evidence.scope || '按各身份关联模式分别查看结果。系统网络事件数量不能证明跨层工具关联。')}</p><div class="card-bottom"><span>原生 ID ${number(evidence.native_tools)}</span><span>系统 ID ${number(evidence.system_tools)}</span></div>${source?`<p class="card-source">${fileLink(source.url,'原始关联报告')}</p>`:''}</article>`;
}
function readinessCard(detail) {
  const items = detail.readiness?.items || [];
  const present = items.filter(item=>tone(item.status)==='good').length;
  return `<article class="evidence-card"><div class="label">03 / 证据完整性 <span class="count-label">本次运行</span></div><h2>工件可追溯程度</h2><div class="metric">${items.length?present:'未知'}${items.length?`<small>/ ${items.length} 项有证据</small>`:''}</div><p>由原始文件、采集摘要与报告是否存在决定。实验成功结论以各项实际证据为准。</p><div class="card-bottom"><span>${detail.database?.files?.length || 0} 个 SQLite</span><span>${detail.artifacts?.length || 0} 个可查看工件</span></div></article>`;
}
function renderOverview(detail) {
  const error = detail.error?.message ? `<div class="note error" style="margin-bottom:20px"><strong>本次运行${isActive(detail)?'提示':'未完整结束'}</strong>${detail.error.stage?` · 阶段 <code>${escapeText(detail.error.stage)}</code>`:''}<br>${escapeText(detail.error.message)}${detail.error.exit_code!=null?`（退出码 ${escapeText(detail.error.exit_code)}）`:''}</div>` : '';
  const counts = detail.database?.counts || {};
  return `${error}<div class="grid-3 evidence-grid">${apiCard(detail)}${correlationCard(detail)}${readinessCard(detail)}</div>${detail.summary?`<div class="note" style="margin-bottom:20px">${escapeText(detail.summary)}</div>`:''}<div class="grid-equal"><section class="panel"><div class="panel-heading"><div><h2>跨层关联模式</h2><p>accepted 与 abstain 分开显示，保留方法适用范围</p></div><a class="inline-link" href="#run/${encodeURIComponent(detail.id)}/traces">查看 Trace →</a></div>${renderCorrelationChart(detail.correlation)}<p class="source-hint">“拒绝推断（abstain）”表示该方法证据不足。受控 Bash 进程桥接独立列出。</p></section><section class="panel"><div class="panel-heading"><div><h2>系统采集记录</h2><p>从所选运行 SQLite 读取的实际行数</p></div><a class="inline-link" href="#run/${encodeURIComponent(detail.id)}/data">打开数据库 →</a></div>${renderCountChart(counts)}</section></div>${renderCorrelationProof(detail)}${renderValidation(detail)}<div class="grid-2"><section class="panel"><div class="panel-heading"><h2>本次使用的真实输入</h2><a class="inline-link" href="#run/${encodeURIComponent(detail.id)}/data">查看源文件 →</a></div>${datasetCard(detail.dataset)}</section><section class="panel"><div class="panel-heading"><h2>证据检查</h2><span class="count-label">工件驱动</span></div>${renderReadiness(detail)}</section></div><section class="panel"><div class="panel-heading"><div><h2>运行过程</h2><p>启动、采集、分析与结束均保留事件记录</p></div>${isActive(detail)?badge('running','实时更新'):''}</div>${renderTimeline(detail.timeline)}</section>`;
}
function renderCorrelationProof(detail) {
  const links=detail.correlation?.links || [];
  if(!links.length)return '';
  const db=Math.max(0,(detail.database?.files || []).findIndex(file=>(file.tables || []).some(table=>table.name==='tool_calls')));
  return `<section class="panel"><div class="panel-heading"><div><h2>工具 ID 匹配证据</h2><p>应用侧原生工具 ID → 本次 SQLite 中的精确工具记录</p></div><button class="button small open-db-proof" data-db="${db}" data-table="tool_calls">查看 tool_calls ↗</button></div><div class="table-wrap"><table class="proof-table"><thead><tr><th>Agent / 会话</th><th>原生工具 ID</th><th>关联结论</th><th>SQLite 行引用</th></tr></thead><tbody>${links.slice(0,20).map(link=>`<tr><td>${escapeText(link.agent_id || '未记录')}<small class="subline mono">${escapeText(link.session_id || '')}</small></td><td><code>${escapeText(link.tool_call_id || '未记录')}</code></td><td>${badge(link.status,link.status==='accepted'?'已匹配':link.status==='abstain'?'拒绝推断':link.status || '未知')}</td><td><details><summary>${link.target_ref?'查看精确引用':'暂无匹配目标'}</summary><p class="source-hint"><code>${escapeText(link.target_ref || link.reason || '未记录')}</code></p>${link.session_system_pid?`<p class="source-hint">会话系统 PID：${escapeText(link.session_system_pid)}</p>`:''}</details></td></tr>`).join('')}</tbody></table></div><p class="source-hint">来源为 session-and-tool 对齐输出${links.length>20?`，预览前 20 / ${links.length} 条`:''}。打开原始报告或 tool_calls 表可逐条核对。</p></section>`;
}
function renderValidation(detail) {
  const validation=detail.validation || {},score=validation.score,prediction=validation.prediction || {};
  if(!score)return '';
  const edge=value=>value?`${value.from || '?'} → ${value.to || '?'}`:'未记录';
  const checks=[['故障类型',score.fault_type_exact],['责任 Agent',score.responsible_agent_exact],['责任步骤',score.responsible_step_exact],['责任边',score.responsible_edge_exact],['传播边',score.propagation_edge_exact]].filter(([,value])=>value!==undefined && value!==null);
  return `<section class="panel"><div class="panel-heading"><div><h2>任务与归因结果 · 应用侧</h2><p>与执行前冻结真值对照的单场景结果，独立于跨层关联结论</p></div>${badge(score.all_attribution_fields_exact===true?'verified':'partial',score.all_attribution_fields_exact===true?'本场景精确匹配':'查看字段结果')}</div><div class="grid-equal"><dl class="detail-list"><dt>故障类型</dt><dd>${escapeText(prediction.fault_type || '未记录')}</dd><dt>责任 Agent</dt><dd>${escapeText(prediction.responsible_agent || '未记录')}</dd><dt>责任步骤</dt><dd><code>${escapeText(prediction.responsible_step || '未记录')}</code></dd><dt>传播边</dt><dd><code>${escapeText(edge(prediction.propagation_edge))}</code></dd></dl><div>${checks.map(([name,passed])=>`<div class="stat-pair"><span>${escapeText(name)}</span><strong>${passed?'匹配':'未匹配'}</strong></div>`).join('')}</div></div><p class="source-hint">${escapeText(score.scope || '仅解释本次受控场景；不外推到其他样本。')}${score.task_failure_observed===true?' · 已观察到场景设定的任务失败；平台运行状态在页首显示。':''}</p></section>`;
}
function renderCorrelationChart(evidence) {
  const modes = Object.entries(evidence?.modes || {}).filter(([,value])=>value);
  if (evidence?.process_bridge && (evidence.process_bridge.accepted!=null || evidence.process_bridge.abstain!=null)) modes.push(['受控 Bash 进程桥',evidence.process_bridge]);
  if (!modes.length) return empty('本次尚无关联结果','采集完成并生成对齐报告后，这里会显示每种关联模式的实际匹配结果。');
  const max = Math.max(1,...modes.map(([,value])=>Number(value.accepted || 0)+Number(value.abstain || 0)));
  const width=540,left=164,right=42,barWidth=width-left-right,height=modes.length*48+20;
  return `<div class="chart-legend"><span><i></i>已匹配 accepted</span><span><i class="abstain"></i>拒绝推断 abstain</span></div><svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="跨层关联模式匹配与拒绝推断数量">${modes.map(([name,value],index)=>{
    const y=index*48+10,a=Number(value.accepted || 0),b=Number(value.abstain || 0),aWidth=a/max*barWidth,bWidth=b/max*barWidth;
    return `<text x="0" y="${y+13}" fill="#6d8591" font-size="10">${escapeText(name)}</text><rect x="${left}" y="${y}" width="${barWidth}" height="21" rx="4" fill="#f3f6f8"/><rect x="${left}" y="${y}" width="${aWidth}" height="21" rx="3" fill="${name.includes('Bash')?'#82a8c8':'#369d86'}"/><rect x="${left+aWidth}" y="${y}" width="${bWidth}" height="21" rx="3" fill="#d8e1e6"/><text x="${width-1}" y="${y+14}" fill="#607e8c" font-size="11" text-anchor="end">${number(value.accepted)} / ${number(value.abstain)}</text>`;
  }).join('')}</svg><p class="table-meta">右侧数字依次为 accepted / abstain。空缺显示为“未知”。</p>`;
}
function renderCountChart(counts) {
  const entries = Object.entries(counts).filter(([,value])=>value!==null && value!==undefined).sort((a,b)=>Number(b[1])-Number(a[1])).slice(0,7);
  if (!entries.length) return empty('本次尚无系统采集表','数据库生成后自动更新。没有数据库时，调用状态仍以调用摘要为准。');
  const max=Math.max(1,...entries.map(([,value])=>Number(value))), width=540,left=146,right=50,space=width-left-right,height=entries.length*32+9;
  return `<svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="SQLite 数据表真实行数">${entries.map(([name,value],i)=>`<text x="0" y="${i*32+17}" fill="#78909d" font-size="10">${escapeText(name)}</text><rect x="${left}" y="${i*32+6}" width="${space}" height="12" rx="3" fill="#f0f4f6"/><rect x="${left}" y="${i*32+6}" width="${Math.max(0,Number(value)/max*space)}" height="12" rx="3" fill="#8faebb"/><text x="${width-1}" y="${i*32+17}" fill="#637f8d" font-size="11" text-anchor="end">${number(value)}</text>`).join('')}</svg><p class="source-hint">记录数量用于确认采集内容，不直接代表 API 成功或关联成功。</p>`;
}
function datasetCard(dataset) {
  if (!dataset) return empty('未登记数据集','这次历史运行的输入尚未登记。可从文件页检查原始工件。');
  return `<div class="dataset-summary"><span class="dataset-icon" aria-hidden="true">▤</span><div><h3>${escapeText(dataset.name || dataset.id)}</h3><p><code>${escapeText(dataset.id)}</code> · ${escapeText(inputNames[dataset.input_kind] || dataset.input_kind || '本地输入')}</p></div>${fileLink(dataset.source_url,'打开原始文件','button small')}</div><p class="dataset-description">${escapeText(dataset.description || '按登记的本地输入执行实验。')}</p><dl class="detail-list"><dt>原始文件</dt><dd><code>${escapeText(dataset.source_path || '未记录')}</code></dd><dt>记录 / 场景数</dt><dd>${number(dataset.record_count)}${/recipe|scenario|场景|脚本|受控/i.test(dataset.input_kind || '')?' 个受控场景':''}</dd><dt>执行方式</dt><dd>${escapeText(typeNames[dataset.experiment_type] || dataset.experiment_type || '未登记')}</dd>${dataset.original_source_url?`<dt>公开输入来源</dt><dd>${fileLink(dataset.original_source_url,'打开来源文件')}</dd>`:''}</dl>`;
}
function renderReadiness(detail) {
  const items=detail.readiness?.items || [];
  if (!items.length) return empty('尚无检查结果','运行工件生成后显示证据是否完整。');
  return items.map(item=>`<div class="readiness-row"><span class="check-icon ${tone(item.status)}" aria-hidden="true">${tone(item.status)==='good'?'✓':tone(item.status)==='bad'?'×':'○'}</span><div><strong>${escapeText(item.name)}</strong><p>${escapeText(item.detail)}</p></div>${badge(item.status,item.status==='not_required'?'不适用':tone(item.status)==='good'?'有证据':tone(item.status)==='bad'?'缺失':'待核验')}</div>`).join('');
}
function renderTimeline(events) {
  if (!events?.length) return empty('尚无过程事件','历史导入记录可能仅保留最终工件；新运行会持续记录各阶段。');
  return `<ol class="timeline">${events.slice(-18).map(event=>`<li><time>${date(event.at,true)}</time><strong>${escapeText(event.stage || '事件')}</strong><p>${escapeText(event.message)}</p></li>`).join('')}</ol>`;
}
function renderTraces(detail) {
  const traces=detail.traces || [];
  const known=traces.filter(trace=>trace.start_ms!=null && trace.duration_ms!=null);
  const min=known.length?Math.min(...known.map(trace=>Number(trace.start_ms))):0,max=known.length?Math.max(...known.map(trace=>Number(trace.start_ms)+Number(trace.duration_ms))):1,span=Math.max(1,max-min);
  const agents=[...new Set(traces.map(trace=>trace.agent).filter(Boolean))];
  return `<section class="panel"><div class="panel-heading"><div><h2>本次运行的 Trace</h2><p>来自已有采集事件。点击行查看原始记录字段。</p></div><span class="count-label">${traces.length} 条已加载</span></div>${traces.length?`<div class="trace-summary"><div><strong>${number(traces.length)}</strong>事件 / span</div><div><strong>${number(agents.length)}</strong>已记录 Agent</div><div><strong>${known.length?number(span/1000)+' s':'未知'}</strong>记录覆盖时长</div></div><div class="chart-legend">${agents.map((agent,i)=>`<span><i style="background:${i%2?'#8caacb':'#82bcae'}"></i>${escapeText(agent)}</span>`).join('')}</div><div class="trace-list">${traces.map(trace=>{
    const timed=trace.start_ms!=null && trace.duration_ms!=null;
    const start=timed?Math.max(0,(Number(trace.start_ms)-min)/span*100):0,width=timed?Math.max(.3,Math.min(100-start,Number(trace.duration_ms)/span*100)):100;
    return `<details class="trace-row"><summary><div class="trace-info"><div class="trace-name"><strong>${escapeText(trace.name || trace.id || '未命名事件')}</strong><small>${escapeText(trace.agent || '未标记 Agent')} · ${escapeText(trace.source || '采集工件')}</small></div><span class="trace-time">${trace.duration_ms==null?'时长未记录':number(Number(trace.duration_ms)/1000)+' s'} ${trace.status?` · ${escapeText(trace.status)}`:''}</span></div><div class="trace-track"><span class="trace-bar ${agents.indexOf(trace.agent)%2?'agent-b':''} ${tone(trace.status)==='bad'?'failed':''}" style="left:${start}%;width:${width}%;${timed?'':'opacity:.35'}"></span></div></summary><pre class="trace-detail">${escapeText(typeof trace.detail==='string'?trace.detail:JSON.stringify(trace.detail || trace,null,2))}</pre></details>`;
  }).join('')}</div>`:empty('这次运行没有可展示的 Trace','可能尚未开始采集，或只保留了摘要。请在数据页检查 SQLite，在文件页查看采集报告。')}<p class="source-hint section-space">时间线使用原生流的本地接收时间，并非工具原始执行时钟；未记录时长的事件以浅色整行表示。</p></section>${renderCorrelationProof(detail)}<div class="grid-equal"><section class="panel"><div class="panel-heading"><h2>关联模式结果</h2></div>${renderCorrelationChart(detail.correlation)}</section><section class="panel"><div class="panel-heading"><h2>采集与分析过程</h2></div>${renderTimeline(detail.timeline)}</section></div>`;
}
function renderData(detail) {
  const files=detail.database?.files || [];
  if (state.db>=files.length) state.db=0;
  const current=files[state.db];
  if (!current?.tables?.some(table=>table.name===state.table)) state.table=current?.tables?.[0]?.name || '';
  return `<section class="panel"><div class="panel-heading"><div><h2>真实输入与原始文件</h2><p>先确认输入内容，再解释这次运行的结果</p></div></div>${datasetCard(detail.dataset)}${detail.dataset?.source_url?'<div class="section-space"><button class="button small" id="show-dataset-source">直接预览源文件</button></div><div id="dataset-source-preview" class="section-space" hidden></div>':''}</section><div class="data-grid"><section class="panel"><div class="panel-heading"><div><h2>SQLite 原始数据</h2><p>逐库逐表查看本次运行的数据，不混入其他运行</p></div><span class="count-label">${files.length} 个数据库</span></div>${files.length?`<div class="database-controls"><label>数据库<select id="database-select">${files.map((file,i)=>`<option value="${i}" ${i===state.db?'selected':''}>${escapeText(file.name || file.path)}</option>`).join('')}</select></label><label>数据表<select id="table-select">${(current.tables || []).map(table=>`<option value="${escapeText(table.name)}" ${table.name===state.table?'selected':''}>${escapeText(table.name)} · ${number(table.rows)} 行</option>`).join('')}</select></label></div><div id="table-preview"><div class="empty"><span class="spinner"></span><p>正在读取数据表…</p></div></div><details class="disclosure"><summary>数据库文件位置</summary><p class="source-hint"><code>${escapeText(current.path)}</code></p></details>`:empty('本次没有可读 SQLite','有些历史实验仅保留报告；运行失败也可能发生在数据库创建之前。请以本次 API 摘要与错误记录为准。')}</section><aside class="panel"><div class="panel-heading"><h2>数据表概况</h2></div><div class="db-summary">${Object.entries(detail.database?.counts || {}).map(([name,count])=>`<div class="db-summary-row"><span>${escapeText(name)}</span><strong>${number(count)}</strong></div>`).join('') || '<p class="muted">暂无数据表</p>'}</div></aside></div>${renderOutputs(detail)}`;
}
function bindData(detail) {
  $('#database-select')?.addEventListener('change',event=>{state.db=Number(event.target.value);state.table='';renderRun();});
  $('#table-select')?.addEventListener('change',event=>{state.table=event.target.value;loadTable(detail.id);});
  if (state.table) loadTable(detail.id);
  else if ($('#table-preview')) $('#table-preview').innerHTML=empty('数据库没有可展示的数据表','SQLite 文件可读，但尚未创建业务数据表。');
}
async function loadTable(id) {
  const request=++state.tableRequest;
  const table=state.table,db=state.db;
  try {
    const result=await api(`/api/runs/${encodeURIComponent(id)}/tables?db=${db}&table=${encodeURIComponent(table)}`);
    if(request!==state.tableRequest || state.route?.id!==id || state.route?.tab!=='data')return;
    const node=$('#table-preview');if(!node)return;
    const rows=result.rows || [],columns=result.columns || [];
    node.innerHTML=rows.length?`<div class="table-wrap"><table class="db-table"><thead><tr>${columns.map(column=>`<th>${escapeText(column)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${columns.map((column,index)=>{
      const value=Array.isArray(row)?row[index]:row[column];
      return `<td><span class="cell-value">${value===null?'<span class="muted">NULL</span>':escapeText(typeof value==='object'?JSON.stringify(value):value)}</span></td>`;
    }).join('')}</tr>`).join('')}</tbody></table></div><p class="table-meta section-space">${escapeText(table)} · 共 ${number(result.total)} 行 · 当前展示 ${rows.length} 行${result.truncated?'（预览已截取）':''}</p>`:empty('这张表目前是空的',`${table} 有 0 条记录。表为空不代表其他层的采集没有发生。`);
  }catch(error){if(request===state.tableRequest && $('#table-preview'))$('#table-preview').innerHTML=empty('无法读取数据表',error.message);}
}
async function loadDatasetSource(dataset) {
  const node=$('#dataset-source-preview');if(!node)return;
  if(!node.hidden){node.hidden=true;return;}
  node.hidden=false;node.innerHTML='<p class="table-meta">正在读取登记的原始文件…</p>';
  const request=++state.sourceRequest;
  try{
    if(!safeUrl(dataset.source_url))throw new Error('未登记可读取的源文件地址。');
    const response=await fetch(dataset.source_url,{cache:'no-store'});
    if(!response.ok)throw new Error(`无法打开源文件（HTTP ${response.status}）`);
    const text=await response.text();
    if(request!==state.sourceRequest || !node.isConnected)return;
    node.innerHTML=`<pre class="code-preview">${escapeText(text.slice(0,40000))}</pre>${text.length>40000?'<p class="source-hint">页内展示前 40,000 字符。可通过“打开原始文件”查看完整内容。</p>':''}`;
  }catch(error){node.innerHTML=`<div class="note warning">${escapeText(error.message)}</div>`;}
}
function renderOutputs(detail) {
  const outputs=detail.outputs || [];
  if(!outputs.length)return '';
  return `<section class="panel"><div class="panel-heading"><h2>运行产物内容</h2></div>${outputs.map(output=>`<details class="output-preview"><summary>${escapeText(output.name)} ${output.url?fileLink(output.url,'原始文件'):''}</summary><pre class="code-preview">${escapeText(typeof output.content==='string'?output.content:JSON.stringify(output.content,null,2))}</pre></details>`).join('')}</section>`;
}
function renderFiles(detail) {
  const artifacts=detail.artifacts || [];
  const images=artifacts.filter(item=>/image|figure|plot|chart/.test(item.kind || '') || /\.(svg|png|jpe?g|webp)$/i.test(item.name || item.path || ''));
  return `${images.length?`<div class="panel-heading"><div><h2>本次运行的图表</h2><p>直接渲染已有图片工件，可打开原图。</p></div><span class="count-label">${images.length} 个</span></div><div class="image-grid">${images.map(item=>`<figure class="image-card"><a href="${safeUrl(item.url)}" target="_blank" rel="noopener noreferrer"><img src="${safeUrl(item.url)}" alt="${escapeText(item.name)}" loading="lazy"></a><figcaption>${escapeText(item.name)}</figcaption></figure>`).join('')}</div>`:`<div class="note" style="margin-bottom:20px">本次未保存图片工件。总览已根据这次真实 SQLite 行数与关联报告自动绘制图表。</div>`}<section class="panel"><div class="panel-heading"><div><h2>原始工件与报告</h2><p>每个文件都属于当前选择的运行，可直接打开核验。</p></div><span class="count-label">${artifacts.length} 个文件</span></div>${artifacts.length?`<div class="artifact-list">${artifacts.map(item=>`<div class="artifact-row"><span class="file-icon" aria-hidden="true">${escapeText((item.name || '').split('.').pop().toUpperCase().slice(0,4) || 'FILE')}</span><div><strong>${escapeText(item.name)}</strong><p><code>${escapeText(item.path || item.kind || '')}</code></p></div>${fileLink(item.url,'打开','button small')}</div>`).join('')}</div>`:empty('尚未生成可查看的文件','运行过程中生成的摘要、对齐报告、结果与图片会持续出现在这里。')}<details class="disclosure"><summary>本次运行所在目录</summary><p class="source-hint"><code>${escapeText(detail.root_path || '未记录')}</code></p></details></section>${renderOutputs(detail)}`;
}
function formDatasets() {return state.datasets.filter(dataset=>dataset.experiment_type===state.form.type);}
function renderNew() {
  if(!state.form.type)state.form.type=state.types[0]?.id || state.datasets[0]?.experiment_type || 'cross_layer_live';
  if(!formDatasets().some(dataset=>dataset.id===state.form.dataset))state.form.dataset=formDatasets()[0]?.id || '';
  $('#main').innerHTML=`<div class="page-heading"><div><div class="eyebrow">NEW EXPERIMENT</div><h1>启动一次新实验</h1><p>选择真实输入，完成环境检查，为本次运行建立独立记录。</p></div><a class="button" href="#runs">查看历史运行 →</a></div><div class="form-layout"><form class="panel" id="new-run-form"><div class="panel-heading"><h2><span class="step-number">01</span> 实验配置</h2></div><div class="form-field"><label for="experiment-name">实验名称</label><input id="experiment-name" type="text" value="${escapeText(state.form.name)}" maxlength="120" autocomplete="off" placeholder="例如：错误传播 · 第 2 次验证" required><p class="form-help">名称可以重复。平台会为每次执行分配新的运行 ID。</p></div><div class="form-field"><label for="experiment-type">实验类型</label><select id="experiment-type">${state.types.map(type=>`<option value="${escapeText(type.id)}" ${type.id===state.form.type?'selected':''}>${escapeText(type.name || typeNames[type.id] || type.id)}</option>`).join('')}</select></div><div class="form-field"><label for="dataset-select">输入数据集 / 受控场景</label><select id="dataset-select">${formDatasets().map(dataset=>`<option value="${escapeText(dataset.id)}" ${dataset.id===state.form.dataset?'selected':''}>${escapeText(dataset.name)}${dataset.available===false?' · 不可用':''}</option>`).join('')}</select><p class="form-help">每个选项都指向已存在的输入文件。右侧可查看具体内容与原始文件。</p></div><div class="panel-heading section-space"><h2><span class="step-number">02</span> 环境与调用检查</h2><button class="button small" id="preflight-button" type="button">重新检查</button></div><div id="preflight-result"></div><div id="api-consent"></div><div class="launch-footer"><p class="disabled-reason" id="start-reason" aria-live="polite"></p><button class="button primary start-button" id="start-experiment" type="submit" disabled>启动实验 <span aria-hidden="true">→</span></button><p class="form-help">启动后自动进入本次运行。采集、数据库、关联报告与页面将持续更新。</p></div></form><aside><section class="panel"><div class="panel-heading"><h2>所选输入</h2><span class="source-tag">原始来源</span></div><div id="new-dataset-detail"></div></section><div class="note"><strong>每次运行独立记录</strong><br>可重复执行相同名称、类型与数据集。历史结果持续保留，并可从运行列表切换查看。</div></aside></div>`;
  $('#experiment-name').addEventListener('input',event=>{state.form.name=event.target.value;updateStart();});
  $('#experiment-type').addEventListener('change',event=>{state.form.type=event.target.value;state.form.dataset='';state.form.consent=false;state.preflight=null;state.preflightId=null;renderNew();});
  $('#dataset-select').addEventListener('change',event=>{state.form.dataset=event.target.value;state.form.consent=false;state.preflight=null;state.preflightId=null;renderNewDataset();runPreflight();});
  $('#preflight-button').addEventListener('click',runPreflight);
  $('#new-run-form').addEventListener('submit',launch);
  renderNewDataset();renderPreflight();
  if(state.preflightId!==state.form.dataset)runPreflight();else updateStart();
}
function selectedDataset() {return state.datasets.find(dataset=>dataset.id===state.form.dataset);}
function renderNewDataset() {
  const dataset=selectedDataset();
  $('#new-dataset-detail').innerHTML=datasetCard(dataset);
  $('#api-consent').innerHTML=dataset?.api_required?`<label class="consent"><input type="checkbox" id="confirm-api" ${state.form.consent?'checked':''}><span><strong>允许本次实验调用真实 API</strong><br>本次预算 ${money(dataset.budget_usd ?? 0.1)}，每个 CLI 会话费用软上限 $0.05。实际用量以调用摘要记录为准。启动将唤起 WSL 执行已登记的实验命令。</span></label>`:'<div class="note section-space">当前类型执行本地输入与工件核验，不需要调用真实 API。</div>';
  $('#confirm-api')?.addEventListener('change',event=>{state.form.consent=event.target.checked;updateStart();});
}
async function runPreflight() {
  const dataset=selectedDataset();if(!dataset){updateStart();return;}
  const id=dataset.id;
  state.preflightLoading=true;state.preflightId=id;state.preflight=null;renderPreflight();updateStart();
  try{const result=await api('/api/preflight',{dataset_id:id});if(state.form.dataset!==id)return;state.preflight=result;}
  catch(error){if(state.form.dataset!==id)return;state.preflight={ok:false,checks:[{name:'服务检查',ok:false,detail:error.message}]};}
  finally{if(state.form.dataset===id){state.preflightLoading=false;if(state.route?.view==='new'){renderPreflight();updateStart();}}}
}
function renderPreflight() {
  const node=$('#preflight-result');if(!node)return;
  $('#preflight-button').disabled=state.preflightLoading || state.launching;
  node.innerHTML=state.preflightLoading?'<div class="note"><span class="spinner" style="width:12px;height:12px;vertical-align:middle;margin-right:8px"></span>正在检查输入、WSL、采集器与 CLI 环境…</div>':state.preflight?`<div class="preflight-checks">${(state.preflight.checks || []).map(check=>`<div class="preflight-check"><span class="check-icon ${check.ok?'':'bad'}" aria-hidden="true">${check.ok?'✓':'×'}</span><div>${escapeText(checkNames[check.name] || check.name)}<p>${escapeText(check.detail)}</p></div></div>`).join('')}</div>`:'<div class="note">选择输入后自动检查运行环境。</div>';
}
function startReason() {
  if(state.launching)return '正在创建独立运行，请稍候…';
  if(!state.form.name.trim())return '请先填写实验名称。';
  const dataset=selectedDataset();
  if(!dataset)return '当前实验类型暂无可用输入，请选择其他类型。';
  if(dataset.available===false)return '登记的输入文件当前不可用，请先恢复原始文件。';
  if(state.preflightLoading)return '正在检查运行环境。';
  if(!state.preflight || state.preflightId!==dataset.id)return '请先完成环境检查。';
  if(!state.preflight.ok)return '环境检查未通过，请根据上方具体原因处理后重新检查。';
  if(dataset.api_required && state.runs.some(run=>isActive(run) && state.datasets.find(item=>item.id===run.dataset_id)?.api_required))return '已有真实 API 实验正在运行，结束后即可再次启动。';
  if(dataset.api_required && !state.form.consent)return '请勾选本次真实 API 调用授权。';
  return '';
}
function updateStart() {
  const reason=startReason(),button=$('#start-experiment');if(!button)return;
  button.disabled=Boolean(reason);$('#start-reason').textContent=reason || '检查通过，可以创建新的实验运行。';
  $('#start-reason').style.color=reason?'':'var(--accent)';
  button.innerHTML=state.launching?'<span class="spinner" style="width:13px;height:13px"></span> 正在启动…':'启动实验 <span aria-hidden="true">→</span>';
}
async function launch(event) {
  event.preventDefault();
  if(startReason()){updateStart();return;}
  state.launching=true;updateStart();
  try{
    const result=await api('/api/runs',{name:state.form.name.trim(),dataset_id:state.form.dataset,experiment_type:state.form.type,confirm_api:state.form.consent});
    const id=result.id || result.run?.id;
    if(!id)throw new Error('服务未返回运行 ID，请在历史运行中检查记录。');
    state.form.consent=false;state.preflight=null;state.preflightId=null;
    await refreshRuns();location.hash=`run/${encodeURIComponent(id)}/overview`;toast('已创建独立运行，正在执行实验。');
  }catch(error){toast(error.message);}
  finally{state.launching=false;if(state.route?.view==='new')updateStart();}
}
async function refreshRuns() {
  const result=await api('/api/runs');state.runs=result.runs || [];renderSidebar();
  if(state.route?.view==='runs')renderRunList();
  if(state.route?.view==='new')updateStart();
}
async function poll() {
  if(state.polling || document.hidden)return;
  state.polling=true;
  try{await refreshRuns();if(state.route?.view==='run' && (isActive(state.detail) || isActive(state.runs.find(run=>run.id===state.route.id))))await loadDetail(state.route.id,true);setConnection(true);}
  catch(error){setConnection(false);}
  finally{state.polling=false;}
}
async function boot() {
  window.addEventListener('hashchange',navigate);
  $('#rescan-button').addEventListener('click',async event=>{event.currentTarget.disabled=true;try{const result=await api('/api/rescan',{});state.runs=result.runs || [];renderSidebar();if(state.route?.view==='runs')renderRunList();if(state.route?.view==='run')await loadDetail(state.route.id);toast('已重新扫描本地实验工件。');}catch(error){toast(error.message);}finally{event.currentTarget.disabled=false;}});
  try{
    const [health,catalog,runs]=await Promise.all([api('/api/health'),api('/api/catalog'),api('/api/runs')]);
    if(health.platform!=='agentops-observatory' || !String(health.version).startsWith('2.'))throw new Error('当前连接的仍是旧版服务。请运行此目录下的 Start-Observatory.ps1，再使用脚本打开的新地址。');
    state.datasets=catalog.datasets || [];state.types=catalog.experiment_types || [];
    if(!state.types.length)state.types=[...new Set(state.datasets.map(dataset=>dataset.experiment_type))].map(id=>({id,name:typeNames[id] || id}));
    state.runs=runs.runs || [];setConnection(true);
    if(!location.hash || ['#overview','#experimentSetup','#traces','#researchGates','#evidence'].includes(location.hash)){
      const preferred=state.runs.find(run=>run.id.includes('20261022-45') || run.id.includes('run45')) || state.runs[0];
      history.replaceState(null,'',preferred?`#run/${encodeURIComponent(preferred.id)}/overview`:'#new');
    }
    await navigate();setInterval(poll,2000);
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll();});
  }catch(error){setConnection(false);$('#main').innerHTML=`<div class="panel page-error"><div class="eyebrow">LOCAL SERVICE</div><h1>无法连接新版实验服务</h1><p class="dataset-description">${escapeText(error.message)}</p><div class="note">在此项目目录运行 <code>powershell -ExecutionPolicy Bypass -File .\Start-Observatory.ps1</code>，然后打开启动脚本提供的地址。</div><button class="button section-space" id="retry-connection">重新连接</button></div>`;$('#retry-connection').addEventListener('click',()=>location.reload());}
}
boot();
