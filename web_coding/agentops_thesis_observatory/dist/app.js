const $=(s,p=document)=>p.querySelector(s);const $$=(s,p=document)=>[...p.querySelectorAll(s)];
const fmt=n=>new Intl.NumberFormat('zh-CN',{maximumFractionDigits:3}).format(n);
const statusLabel={verified:'VERIFIED',warning:'WARNING',partial:'PARTIAL',blocked:'BLOCKED','not-started':'NOT STARTED',implementation:'IMPLEMENTED'};
const DRAFT_KEY='agentops-experiment-input-drafts-v1';
const escapeHtml=value=>String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
let DATA,DRAFTS=[],PREFLIGHT=null,ACTIVE_RUN=null,SELECTED_RUN=null,POLL_TIMER=null,CONTROLLER_READY=false;

async function init(){
  const res=await fetch('data.json',{cache:'no-store'}); if(!res.ok) throw new Error('data.json unavailable'); DATA=await res.json();
  renderHeader();renderMetrics();renderCapabilities();renderBudget();renderTrace();renderTestChart();renderCaptureIntegrity();renderIdentity();renderClock();renderEvidence();renderQuality();renderDatasetForm();renderExperiments(DATA.experiments);bindUI();await connectController();
}

function renderHeader(){
  $('#snapshotTime').textContent=DATA.meta.generatedAt.replace('T',' ').replace('+08:00',' CST');
  $('#gateStatus').textContent=DATA.headline.gate;
  $('#sourceCount').textContent=`${DATA.sources.length} TRACEABLE SOURCES`;
}

function renderMetrics(){
  const h=DATA.headline, cards=[
    ['Current experiments',DATA.meta.currentExperiments,'已登记实验记录','var(--cyan)'],
    ['Field completeness',`${h.fieldCompleteness*100}%`,`${DATA.quality.overallPresent}/${DATA.quality.overallExpected} required slots`,'var(--lime)'],
    ['Direct PID mapping',`${h.directPid.initial} → ${h.directPid.collector}`,'initial NS → collector NS','var(--purple)'],
    ['Clock floor',`${h.clockFloorNs} ns`,'nonzero uncertainty bound','var(--cyan)'],
    ['Query replay',h.queryReplay,'hash-identical receipts','var(--lime)'],
    ['Passing tests',h.testsPassed,'0 failed · recorded suite','var(--orange)']
  ];
  $('#metricGrid').innerHTML=cards.map(([label,value,detail,color])=>`<article class="metric" style="--accent:${color}"><label>${label}<i></i></label><strong>${value}</strong><small>${detail}</small></article>`).join('');
}

function renderCapabilities(){
  const colors={verified:'var(--lime)',implementation:'var(--cyan)',blocked:'var(--red)','not-started':'var(--muted)'};
  $('#capabilityList').innerHTML=DATA.capabilities.map(x=>`<div class="capability"><div class="capability-name"><strong>${x.name}</strong><small>${x.detail}</small></div><div class="capability-track"><i style="width:${x.score*100}%;--cap:${colors[x.status]}"></i></div><span class="capability-status">${statusLabel[x.status]}</span></div>`).join('');
}

function renderBudget(){
  const b=DATA.headline.budget,max=Math.max(b.projected,b.limit),spent=Math.min(100,b.spent/max*100),limit=b.limit/max*100;
  $('#spentCost').textContent=b.spent.toFixed(4);$('#limitCost').textContent=`batch stop $${b.limit.toFixed(3)}`;$('#projectedCost').textContent=`plan ¥${b.plannedBatchCny}/${b.batchCapCny}`;$('#budgetFill').style.width=`${spent}%`;$('#budgetLimit').style.left=`${limit}%`;
  const badge=$('.budget-panel .status-tag');badge.textContent=b.status;badge.className=`status-tag ${b.status==='PARTIAL'?'partial':'blocked'}`;
  $('#budgetNote').textContent=typeof b.reportedIncrementalUsd==='number'?`本批次 CLI 报告增量 $${b.reportedIncrementalUsd.toFixed(6)}，按规划系数约 ¥${b.reportedIncrementalCnyAtRate.toFixed(2)}；历史冻结账本仍未完全复核，不是最终账单。`:b.ledgerReconciled?'当前批次仍须完成运行环境和实时费用预检。':'旧账本原始日志尚未复核；本批次仅规划增量费用，不代表已经发生调用。';
}

function renderTrace(){
  const t=DATA.trace;
  $('#traceMeta').innerHTML=[['RUN',t.runId],['SESSION',t.sessionId],['EVENTS',t.eventCount],['DURATION',`${t.durationMs} ms`],['STATUS',t.closed?'CLOSED':'OPEN']].map(([k,v])=>`<div><span>${k}</span><strong>${v}</strong></div>`).join('');
  const color={session:'var(--cyan)',step:'var(--cyan)',tool:'var(--purple)',system:'var(--lime)'};
  $('#traceRows').innerHTML=t.spans.map((s,i)=>`<div class="trace-row"><div class="trace-name"><strong>${s.name}</strong><small>${s.type} · ${s.status}</small></div><div class="trace-lane"><button class="span" data-span="${i}" aria-label="查看 ${s.name}" style="left:${s.start}%;width:${s.duration}%;--span:${color[s.type]}"></button></div></div>`).join('');
  $('#lifecycle').innerHTML=t.lifecycle.map(x=>`<div class="life-event">${x}</div>`).join('');
  $$('.span').forEach(btn=>btn.addEventListener('click',()=>inspectSpan(Number(btn.dataset.span),btn)));
}

function renderCaptureIntegrity(){
  const c=DATA.captureIntegrity,a=c.aggregate;
  $('#captureSummary').innerHTML=[
    ['诊断运行',`${a.runs} 次`,'本地报告汇总'],
    ['工具捕获',`${a.capturedToolCalls}/${a.nativeToolCalls}`,`缺失 ${a.missingToolCalls} 次 · ${fmt(a.coverage*100)}%`],
    ['缺失 ID 命中 SQLite',`${a.missingIdsInSqlite}/${a.missingToolCalls}`,'任一表均未命中'],
    ['具体根因','未确定','采集前/写入过程为推断']
  ].map(([label,value,detail])=>`<article class="metric"><label>${label}<i></i></label><strong>${value}</strong><small>${detail}</small></article>`).join('');
  $('#captureScenarioRows').innerHTML=c.scenarios.map(x=>`<tr><td>${x.scenario}</td><td>${x.systemCalls}/${x.nativeCalls}</td><td>${x.missingStep}</td><td><span class="status-tag ${x.systemAlignment==='accepted'?'verified':'warning'}">${x.systemAlignment.toUpperCase()}</span></td></tr>`).join('');
  $('#captureObservations').innerHTML=c.observations.map((x,i)=>`<div class="capture-observation"><span>${i<2?'VERIFIED REPORT':'EVIDENCE LIMIT'}</span><p>${x}</p></div>`).join('')+`<div class="capture-observation inferred"><span>INFERRED / UNVERIFIED</span><p>${c.inference}</p></div><div class="capture-observation"><span>NEW EXPERIMENT INSTRUMENTATION</span><p>${c.futureInstrumentation}</p><p><strong>下一闸门：</strong>${c.nextGate}</p></div>`;
  $('#captureRawNote').textContent=c.rawEvidenceNote;
  if(!c.reproducedFromRawRuns) $('#captureStatus').textContent='ROOT CAUSE UNRESOLVED';
  const p=DATA.datasetExpansion;
  $('#scalePlanSummary').innerHTML=[
    ['公开适配记录',p.publicAdapterRecords,'schema/标签兼容，不是跨层实测'],
    ['计划新增真实场景',p.plannedAdditionalRuns,`${p.realFaultClasses} 类 × ${p.plannedAdditionalRepeatsPerClass} 次`],
    ['离线合成压力样例',p.syntheticFixtureCount,`API 0 次 · 未运行生产对齐器`],
    ['单场景上限',`${p.perExperimentCapCny} CNY`,`计划上界 ${p.perExperimentPlannedUpperCny} CNY`],
    ['本批次上界',`${p.plannedBatchUpperCny} CNY`,'未执行；需累计预算预检']
  ].map(([label,value,detail])=>`<article class="metric"><label>${label}<i></i></label><strong>${value}</strong><small>${detail}</small></article>`).join('');
  $('#scalePlanNote').textContent=`旧九场景扩样计划：${p.note} 历史累计 $${p.historicalSpendUsd}，当时硬停止线 $${p.existingHardStopUsd}；与当前小样本批次分开核算。旧九场景计划未授权从本页执行。`;
}

function inspectSpan(index,button){
  $$('.span').forEach(x=>x.classList.remove('selected'));button.classList.add('selected');const s=DATA.trace.spans[index];
  $('#spanInspector').innerHTML=`<div class="panel-head"><div><span class="panel-kicker">SPAN INSPECTOR</span><h3>${s.name}</h3></div><span class="status-tag verified">${s.status.toUpperCase()}</span></div><dl><dt>Span type</dt><dd>${s.type}</dd><dt>Relative start</dt><dd>${s.start}%</dd><dt>Relative width</dt><dd>${s.duration}%</dd><dt>Evidence</dt><dd>${s.evidence}</dd><dt>Run</dt><dd>${DATA.trace.runId}</dd><dt>Claim boundary</dt><dd>structural observation; no causal attribution</dd></dl>`;
}

function renderTestChart(){
  const d=DATA.testProgression,w=560,h=190,p=28,max=Math.max(...d.map(x=>x.value))+10,min=Math.min(...d.map(x=>x.value))-10;
  const points=d.map((x,i)=>({x:p+i*(w-2*p)/(d.length-1),y:h-p-(x.value-min)/(max-min)*(h-2*p),...x}));
  const line=points.map((x,i)=>`${i?'L':'M'}${x.x},${x.y}`).join(' '),area=`${line} L${points.at(-1).x},${h-p} L${points[0].x},${h-p} Z`;
  $('#testChart').innerHTML=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="测试通过数量增长"><defs><linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="var(--lime)" stop-opacity=".22"/><stop offset="1" stop-color="var(--lime)" stop-opacity="0"/></linearGradient></defs>${[0,.5,1].map(v=>`<line class="grid-line" x1="${p}" x2="${w-p}" y1="${p+v*(h-2*p)}" y2="${p+v*(h-2*p)}"/>`).join('')}<path class="area" d="${area}"/><path class="chart-line" d="${line}"/>${points.map(x=>`<circle cx="${x.x}" cy="${x.y}" r="4"/><text x="${x.x}" y="${x.y-12}" text-anchor="middle">${x.value}</text><text x="${x.x}" y="${h-7}" text-anchor="middle">${x.label}</text>`).join('')}</svg>`;
}

function renderIdentity(){
  const i=DATA.identity;$('#initialPid').textContent=i.initialPid;$('#collectorPid').textContent=i.collectorPid;$('#mappingMethod').textContent=`bpf.pidns.tgid=${i.initialPid},${i.collectorPid} · ${i.mappingMethod}`;
  $('#identityChecks').innerHTML=Object.entries(i.checks).map(([k,v])=>`<div class="check-item"><i>${v?'✓':'×'}</i>${k.replaceAll('_',' ')}</div>`).join('');
  $('#identityGraph').innerHTML=`<div class="panel-head"><div><span class="panel-kicker">CROSS-LAYER GRAPH</span><h3>Session → process → namespace</h3></div><span class="micro">DIRECT EDGE IN LIME</span></div><svg viewBox="0 0 650 300" role="img" aria-label="跨层身份映射图"><line class="edge" x1="120" y1="80" x2="320" y2="150"/><line class="edge direct" x1="320" y1="150" x2="525" y2="75"/><line class="edge direct" x1="320" y1="150" x2="525" y2="230"/><rect class="node" x="35" y="43" width="170" height="74" rx="13"/><text x="55" y="72">framework session</text><text class="sub" x="55" y="94">runtime observed</text><rect class="node accepted" x="235" y="113" width="170" height="74" rx="13"/><text x="255" y="142">EXEC event</text><text class="sub" x="255" y="164">unique marker match</text><rect class="node accepted" x="445" y="37" width="170" height="74" rx="13"/><text x="465" y="67">initial namespace</text><text class="sub" x="465" y="89">PID ${i.initialPid}</text><rect class="node accepted" x="445" y="193" width="170" height="74" rx="13"/><text x="465" y="223">collector namespace</text><text class="sub" x="465" y="245">PID ${i.collectorPid} = userspace</text></svg>`;
}

function renderClock(){
  const c=DATA.clock;$('#clockFloor').textContent=c.anchorUncertaintyNs;$('#clockFormula').textContent=`${c.bootEpochNs} + ${c.rawBootNs}`;
  const max=Math.max(...c.series.map(x=>x.anchorRangeNs));$('#clockBars').innerHTML=c.series.map(x=>`<div class="bar-wrap" title="${fmt(x.anchorRangeNs)} ns"><div class="bar" style="height:${Math.max(3,x.anchorRangeNs/max*100)}%"></div><span>${x.experiment}</span></div>`).join('');
}

function renderEvidence(){
  $('#handlerList').innerHTML=DATA.evidence.handlers.map(x=>{const bad=x.status==='unavailable',warn=x.status.includes('without')||x.status.includes('inference');return `<div class="handler"><div class="handler-head"><strong>${x.channel}</strong><i class="tiny-dot ${bad?'blocked':warn?'warning':''}"></i></div><p>${x.handler_id}</p><p>${x.status.replaceAll('_',' ')}</p></div>`}).join('');
  $('#queryList').innerHTML=DATA.evidence.queries.map(x=>`<div class="query"><div class="query-head"><strong>${x.query_id}</strong><span class="hash">${x.result_sha256.slice(0,8)}</span></div><p>${x.purpose}</p><p>${x.result_count} event${x.result_count===1?'':'s'} · exact selector</p></div>`).join('');
  $('#relationList').innerHTML=DATA.evidence.relations.map(x=>`<div class="relation"><div class="relation-head"><strong>${x.relation_type}</strong><span class="status-tag ${x.evidence_status==='direct'?'verified':'warning'}">${x.evidence_status.toUpperCase()}</span></div><p>${x.source.kind} → ${x.target.kind}</p><p>${x.query_ids.length} receipt${x.query_ids.length===1?'':'s'} · causal=false</p></div>`).join('');
}

function renderQuality(){
  $('#fieldGroups').innerHTML=Object.entries(DATA.quality.fieldGroups).map(([name,x])=>`<div class="field-group"><strong>${name.replaceAll('_',' ')}</strong><span>${x.present}/${x.expected}</span><div class="field-progress"><i style="width:${x.rate*100}%"></i></div></div>`).join('');
}

function renderDatasetForm(){
  const modeSelect=$('#experimentMode');
  DATA.datasetModes.forEach(mode=>{
    const option=document.createElement('option');option.value=mode.id;option.textContent=mode.label;
    modeSelect.append(option);
  });
  try{
    const stored=JSON.parse(localStorage.getItem(DRAFT_KEY)||'[]');
    DRAFTS=Array.isArray(stored)?stored.filter(x=>x&&typeof x.dataset_id==='string').slice(0,20):[];
  }catch{DRAFTS=[]}
  renderDrafts();
}

function refreshDatasetOptions(){
  const mode=$('#experimentMode').value,select=$('#datasetSelect');
  select.replaceChildren();
  const placeholder=document.createElement('option');placeholder.value='';placeholder.textContent=mode?'请选择本次实验的输入数据集':'先选择实验类型';
  select.append(placeholder);
  DATA.datasetCatalog.filter(dataset=>dataset.mode===mode).forEach(dataset=>{
    const option=document.createElement('option');option.value=dataset.id;
    option.textContent=`${dataset.name} · ${fmt(dataset.recordCount)} 条${dataset.available?'':'（本地文件缺失）'}`;
    option.disabled=!dataset.available;select.append(option);
  });
  select.disabled=!mode;select.value='';renderDatasetDetails(null);clearPreflight();
}

function renderDatasetDetails(dataset){
  const panel=$('#datasetDetails');panel.replaceChildren();
  const kicker=document.createElement('span');kicker.className='panel-kicker';kicker.textContent='DATASET PROVENANCE';panel.append(kicker);
  const heading=document.createElement('h3');heading.textContent=dataset?dataset.name:'尚未选择数据集';panel.append(heading);
  if(!dataset){const empty=document.createElement('p');empty.className='panel-note';empty.textContent='选择后显示样本量、输入路径与能验证的证据范围。';panel.append(empty);return}
  const facts=document.createElement('dl');facts.className='dataset-facts';
  const rows=[['记录数',`${fmt(dataset.recordCount)} 条${dataset.stepCount?` · ${dataset.stepCount} 步`:''}`],['输入路径',dataset.inputPath],['选择范围',dataset.selector],['API 调用',dataset.apiRequired?'仅预检通过后按授权执行':'不需要'],['系统侧配对',dataset.pairedSystemObservations==='on_new_run'?'仅新运行后可验证':dataset.pairedSystemObservations==='synthetic_only'?'仅合成事件':'无本地配对观测']];
  rows.forEach(([key,value])=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=key;dd.textContent=value;facts.append(dt,dd)});panel.append(facts);
  const boundary=document.createElement('p');boundary.className='dataset-boundary';boundary.textContent=`证据边界：${dataset.evidenceBoundary}`;panel.append(boundary);
  const note=document.createElement('p');note.className='panel-note';note.textContent=dataset.executionNote;panel.append(note);
}

function renderDrafts(){
  const list=$('#draftList');list.replaceChildren();
  if(!DRAFTS.length){const empty=document.createElement('p');empty.className='empty-state';empty.textContent='尚无草稿。保存时会记录本次选择的数据集 ID。';list.append(empty)}
  else DRAFTS.forEach(draft=>{
    const row=document.createElement('div');row.className='draft-row';
    const title=document.createElement('strong');title.textContent=draft.experiment_name;
    const detail=document.createElement('span');detail.textContent=`${draft.dataset_name} (${draft.dataset_id}) · ${draft.created_at}`;
    const status=document.createElement('em');status.textContent='NOT STARTED';
    const load=document.createElement('button');load.type='button';load.className='secondary-button';load.textContent='载入';load.addEventListener('click',()=>loadDraft(draft));
    const remove=document.createElement('button');remove.type='button';remove.className='draft-delete';remove.textContent='删除草稿';remove.setAttribute('aria-label',`删除草稿 ${draft.experiment_name}`);
    remove.addEventListener('click',()=>removeDraft(draft.draft_id));
    row.append(title,detail,status,load,remove);list.append(row);
  });
}

function removeDraft(id){
  DRAFTS=DRAFTS.filter(draft=>draft.draft_id!==id);
  try{localStorage.setItem(DRAFT_KEY,JSON.stringify(DRAFTS))}catch{}
  $('#configMessage').textContent='已从当前浏览器删除草稿；实验记录未受影响。';renderDrafts();
}

function loadDraft(draft){
  $('#experimentName').value=draft.experiment_name;
  $('#experimentMode').value=draft.experiment_mode;
  refreshDatasetOptions();
  $('#datasetSelect').value=draft.dataset_id;
  renderDatasetDetails(DATA.datasetCatalog.find(item=>item.id===draft.dataset_id)||null);
  $('#configMessage').textContent='已载入草稿；请重新运行预检，草稿本身不授权 API 调用。';
  $('#experimentSetup').scrollIntoView();
}

function saveExperimentDraft(event){
  event.preventDefault();
  const name=$('#experimentName').value.trim(),mode=$('#experimentMode').value,id=$('#datasetSelect').value;
  const dataset=DATA.datasetCatalog.find(item=>item.id===id&&item.mode===mode&&item.available);
  if(!name||!dataset){$('#configMessage').textContent='请填写实验名称，并为本次实验明确选择一个可用的数据集。';return}
  const now=new Date();
  const draft={schema_version:'agentops-experiment-input-v1',draft_id:`draft-${now.toISOString().replace(/\D/g,'').slice(0,14)}-${Math.random().toString(36).slice(2,6)}`,created_at:now.toISOString(),experiment_name:name,experiment_mode:mode,dataset_id:dataset.id,dataset_name:dataset.name,input_path:dataset.inputPath,selector:dataset.selector,record_count:dataset.recordCount,api_required:dataset.apiRequired,paired_system_observations:dataset.pairedSystemObservations,evidence_boundary:dataset.evidenceBoundary,execution_status:'NOT_STARTED'};
  DRAFTS=[draft,...DRAFTS].slice(0,20);
  try{localStorage.setItem(DRAFT_KEY,JSON.stringify(DRAFTS));$('#configMessage').textContent=`已保存草稿 ${draft.draft_id}；未执行实验或 API 调用。`}
  catch{$('#configMessage').textContent='浏览器本地存储不可用；草稿未持久保存。'}
  renderDrafts();event.target.reset();refreshDatasetOptions();
}

function renderExperiments(rows){
  $('#experimentRows').innerHTML=rows.map(x=>{
    const datasets=(x.datasetIds||[]).map(id=>DATA.datasetCatalog.find(dataset=>dataset.id===id)?.name||id);
    const input=datasets.length?datasets.join(' + ')+(x.datasetEvidence==='planned_only'?' · 计划输入':''):'未登记';
    return `<tr><td>${escapeHtml(x.id)}</td><td>${escapeHtml(x.time)}</td><td class="dataset-cell">${escapeHtml(input)}</td><td>${escapeHtml(x.stage)}</td><td>${escapeHtml(x.metric)}</td><td><span class="status-tag ${x.status}">${statusLabel[x.status]}</span></td><td class="${x.networkCalls===0?'network-zero':''}">${x.networkCalls}</td></tr>`;
  }).join('')||'<tr><td colspan="7">没有匹配记录</td></tr>';
}

async function api(path,options={}){
  const response=await fetch(path,{cache:'no-store',...options});
  const result=await response.json();
  if(!response.ok) throw Object.assign(new Error(result.error||`HTTP ${response.status}`),{detail:result});
  return result;
}

function clearPreflight(){
  PREFLIGHT=null;
  $('#startButton').disabled=true;
  $('#preflightButton').disabled=!$('#datasetSelect').value||!CONTROLLER_READY;
  $('#preflightGates').innerHTML='<p class="empty-state">请选择本次输入数据集，然后运行预检。</p>';
}

async function connectController(){
  try{
    const health=await api('/api/health');
    CONTROLLER_READY=true;
    $('#controllerBadge').textContent='LOCAL CONTROLLER READY';
    $('#controllerBadge').className='status-tag verified';
    await refreshRunList();
    if(health.active_run){ACTIVE_RUN=health.active_run;await pollRun()}
  }catch{
    CONTROLLER_READY=false;
    $('#controllerBadge').textContent='CONTROLLER OFFLINE';
    $('#controllerBadge').className='status-tag blocked';
    $('#preflightButton').disabled=true;
    $('#startButton').disabled=true;
    $('#preflightGates').innerHTML='<p class="panel-note">当前仍是静态页面；请用本地实验控制器启动服务。此状态下不会执行任何实验。</p>';
  }
}

async function checkPreflight(){
  const datasetId=$('#datasetSelect').value;
  if(!datasetId) return;
  $('#preflightButton').disabled=true;
  $('#preflightGates').textContent='正在检查本地输入、预算和运行环境…';
  try{
    const result=await api(`/api/preflight?dataset_id=${encodeURIComponent(datasetId)}`);
    if($('#datasetSelect').value!==datasetId) return;
    PREFLIGHT=result;
    $('#preflightGates').innerHTML=result.gates.map(gate=>`<div class="gate-row ${gate.ok?'pass':'fail'}"><span>${gate.ok?'✓':'×'}</span><strong>${escapeHtml(gate.key)}</strong><p>${escapeHtml(gate.detail)}</p></div>`).join('');
    $('#startButton').disabled=!result.can_start||Boolean(ACTIVE_RUN)||Boolean(result.api_required&&!$('#budgetConfirm').checked);
    $('#configMessage').textContent=result.can_start?'预检通过；可以启动当前所选数据集。':'预检未通过；没有启动实验或 API 调用。';
  }catch(error){
    clearPreflight();$('#configMessage').textContent=`预检失败：${error.message}`;
  }finally{$('#preflightButton').disabled=!$('#datasetSelect').value||!CONTROLLER_READY}
}

async function startExperiment(){
  if(!PREFLIGHT?.can_start||PREFLIGHT.dataset_id!==$('#datasetSelect').value) return;
  const name=$('#experimentName').value.trim();
  if(!name){$('#configMessage').textContent='请先填写实验名称。';return}
  $('#startButton').disabled=true;
  try{
    const response=await api('/api/runs',{method:'POST',headers:{'Content-Type':'application/json','X-AgentOps-Control':'1'},body:JSON.stringify({name,dataset_id:PREFLIGHT.dataset_id,confirm_budget:$('#budgetConfirm').checked})});
    ACTIVE_RUN=response.run_id;
    $('#configMessage').textContent=`实验 ${ACTIVE_RUN} 已进入运行器；请看下方进度。`;
    $('#runStatus').textContent='已启动，等待首个阶段状态…';
    $('#stopFollowup').disabled=!PREFLIGHT.api_required;
    await pollRun();
  }catch(error){
    $('#configMessage').textContent=`未启动：${error.message}`;
    if(error.detail?.preflight){PREFLIGHT=error.detail.preflight;$('#preflightGates').innerHTML=PREFLIGHT.gates.map(g=>`<div class="gate-row ${g.ok?'pass':'fail'}"><span>${g.ok?'✓':'×'}</span><strong>${escapeHtml(g.key)}</strong><p>${escapeHtml(g.detail)}</p></div>`).join('')}
    $('#startButton').disabled=true;
  }
}

function renderRun(state){
  SELECTED_RUN=state;
  const badge=state.status==='COMPLETED'?'verified':state.status==='RUNNING'?'warning':state.status==='PARTIAL'?'partial':'blocked';
  $('#runStatus').innerHTML=`<span class="status-tag ${badge}">${escapeHtml(state.status)}</span> <strong>${escapeHtml(state.name)}</strong> · ${escapeHtml(state.run_id)} · ${escapeHtml(state.stage)}`;
  $('#runEvents').innerHTML=(state.events||[]).map(event=>`<div><time>${escapeHtml(event.at)}</time><strong>${escapeHtml(event.stage)}</strong><span>${escapeHtml(event.message)}</span></div>`).join('');
  $('#runResult').textContent=state.result?JSON.stringify(state.result,null,2):'';
  $('#stopFollowup').disabled=state.status!=='RUNNING'||state.kind!=='authorized_live_batch';
  $('#continueAgentRx').disabled=!(state.kind==='authorized_live_batch'&&state.status==='FAILED'&&state.result?.failed_stage==='error_propagation'&&state.result?.api_calls===2&&!ACTIVE_RUN&&$('#budgetConfirm').checked);
}

async function continueAgentRx(){
  const runId=SELECTED_RUN?.run_id;
  if(!runId||$('#continueAgentRx').disabled) return;
  $('#continueAgentRx').disabled=true;
  try{
    await api(`/api/runs/${runId}/continue-agentrx`,{method:'POST',headers:{'Content-Type':'application/json','X-AgentOps-Control':'1'},body:JSON.stringify({confirm_budget:$('#budgetConfirm').checked})});
    ACTIVE_RUN=runId;
    $('#configMessage').textContent='仅继续原批次尚未执行的 AgentRx 单次诊断；不会重跑双 Agent 会话。';
    await pollRun();
  }catch(error){$('#configMessage').textContent=`AgentRx 未启动：${error.message}`}
}

async function pollRun(){
  if(POLL_TIMER){clearTimeout(POLL_TIMER);POLL_TIMER=null}
  if(!ACTIVE_RUN) return;
  try{
    const state=await api(`/api/runs/${ACTIVE_RUN}`);
    renderRun(state);
    if(state.status==='RUNNING'){
      POLL_TIMER=setTimeout(pollRun,2000);
    }else{
      ACTIVE_RUN=null;PREFLIGHT=null;$('#startButton').disabled=true;$('#stopFollowup').disabled=true;
      await refreshRunList();
    }
  }catch(error){$('#runStatus').textContent=`状态读取失败：${error.message}`;POLL_TIMER=setTimeout(pollRun,4000)}
}

async function refreshRunList(){
  try{
    const runs=await api('/api/runs');
    const list=$('#localRunList');list.replaceChildren();
    if(!runs.length){list.textContent='本机尚无运行记录。';return}
    runs.forEach(run=>{
      const button=document.createElement('button');button.type='button';button.className='run-item';
      button.textContent=`${run.created_at} · ${run.name} · ${run.dataset_id} · ${run.status}`;
      button.addEventListener('click',async()=>{try{renderRun(await api(`/api/runs/${run.run_id}`))}catch(error){$('#runStatus').textContent=error.message}});
      list.append(button);
    });
  }catch(error){$('#localRunList').textContent=`运行记录暂不可用：${error.message}`}
}

async function stopFollowup(){
  if(!ACTIVE_RUN) return;
  try{
    await api(`/api/runs/${ACTIVE_RUN}/stop-after-current`,{method:'POST',headers:{'Content-Type':'application/json','X-AgentOps-Control':'1'},body:'{}'});
    $('#configMessage').textContent='已请求停止后续 API 阶段；当前会话不会被中断。';
    $('#stopFollowup').disabled=true;
  }catch(error){$('#configMessage').textContent=`停止请求失败：${error.message}`}
}

async function refreshSnapshot(){
  try{
    await api('/api/refresh-snapshot',{method:'POST',headers:{'Content-Type':'application/json','X-AgentOps-Control':'1'},body:'{}'});
    $('#configMessage').textContent='证据快照已刷新；页面即将重新加载。';
    location.reload();
  }catch(error){$('#configMessage').textContent=`快照刷新失败：${error.message}`}
}

function bindUI(){
  $('#experimentMode').addEventListener('change',refreshDatasetOptions);
  $('#datasetSelect').addEventListener('change',event=>{renderDatasetDetails(DATA.datasetCatalog.find(item=>item.id===event.target.value)||null);clearPreflight()});
  $('#experimentConfigForm').addEventListener('submit',saveExperimentDraft);
  $('#budgetConfirm').addEventListener('change',()=>{$('#startButton').disabled=!PREFLIGHT?.can_start||Boolean(ACTIVE_RUN)||Boolean(PREFLIGHT?.api_required&&!$('#budgetConfirm').checked);if(SELECTED_RUN) renderRun(SELECTED_RUN)});
  $('#preflightButton').addEventListener('click',checkPreflight);
  $('#startButton').addEventListener('click',startExperiment);
  $('#stopFollowup').addEventListener('click',stopFollowup);
  $('#continueAgentRx').addEventListener('click',continueAgentRx);
  $('#refreshRuns').addEventListener('click',refreshRunList);
  $('#refreshSnapshot').addEventListener('click',refreshSnapshot);
  $('#experimentSearch').addEventListener('input',e=>{const q=e.target.value.toLowerCase();renderExperiments(DATA.experiments.filter(x=>Object.values(x).join(' ').toLowerCase().includes(q)))});
  $('#focusSearch').addEventListener('click',()=>{$('#evaluations').scrollIntoView();setTimeout(()=>$('#experimentSearch').focus(),300)});
  document.addEventListener('keydown',e=>{if(e.key==='/'&&!/input|textarea/i.test(document.activeElement.tagName)){e.preventDefault();$('#focusSearch').click()}});
  $('#themeToggle').addEventListener('click',()=>{const root=document.documentElement;root.dataset.theme=root.dataset.theme==='dark'?'light':'dark'});
  $('#menuButton').addEventListener('click',()=>$('#sidebar').classList.toggle('open'));
  $$('.nav-item').forEach(a=>a.addEventListener('click',()=>{$$('.nav-item').forEach(x=>x.classList.remove('active'));a.classList.add('active');$('#sidebar').classList.remove('open')}));
  const observer=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting){$$('.nav-item').forEach(x=>x.classList.toggle('active',x.dataset.section===e.target.id))}}),{rootMargin:'-35% 0px -55% 0px'});$$('.section').forEach(s=>observer.observe(s));
}

init().catch(err=>{document.body.innerHTML=`<main style="margin:0;padding:40px"><h1>Dashboard data error</h1><pre>${err.message}</pre></main>`});
