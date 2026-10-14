const $=(s,p=document)=>p.querySelector(s);const $$=(s,p=document)=>[...p.querySelectorAll(s)];
const fmt=n=>new Intl.NumberFormat('zh-CN',{maximumFractionDigits:3}).format(n);
const statusLabel={verified:'VERIFIED',warning:'WARNING',partial:'PARTIAL',blocked:'BLOCKED','not-started':'NOT STARTED',implementation:'IMPLEMENTED'};
let DATA;

async function init(){
  const res=await fetch('data.json'); if(!res.ok) throw new Error('data.json unavailable'); DATA=await res.json();
  renderHeader();renderMetrics();renderCapabilities();renderBudget();renderTrace();renderTestChart();renderIdentity();renderClock();renderEvidence();renderQuality();renderExperiments(DATA.experiments);bindUI();
}

function renderHeader(){
  $('#snapshotTime').textContent=DATA.meta.generatedAt.replace('T',' ').replace('+08:00',' CST');
  $('#gateStatus').textContent=DATA.headline.gate;
  $('#sourceCount').textContent=`${DATA.sources.length} TRACEABLE SOURCES`;
}

function renderMetrics(){
  const h=DATA.headline, cards=[
    ['Current experiments',DATA.meta.currentExperiments,'hour-level experiment folders','var(--cyan)'],
    ['Field completeness',`${h.fieldCompleteness*100}%`,`${DATA.quality.overallPresent}/${DATA.quality.overallExpected} required slots`,'var(--lime)'],
    ['Direct PID mapping',`${h.directPid.initial} → ${h.directPid.collector}`,'initial NS → collector NS','var(--purple)'],
    ['Clock floor',`${h.clockFloorNs} ns`,'nonzero uncertainty bound','var(--cyan)'],
    ['Query replay',h.queryReplay,'hash-identical receipts','var(--lime)'],
    ['Passing tests',h.testsPassed,'0 failed · current suite','var(--orange)']
  ];
  $('#metricGrid').innerHTML=cards.map(([label,value,detail,color])=>`<article class="metric" style="--accent:${color}"><label>${label}<i></i></label><strong>${value}</strong><small>${detail}</small></article>`).join('');
}

function renderCapabilities(){
  const colors={verified:'var(--lime)',implementation:'var(--cyan)',blocked:'var(--red)','not-started':'var(--muted)'};
  $('#capabilityList').innerHTML=DATA.capabilities.map(x=>`<div class="capability"><div class="capability-name"><strong>${x.name}</strong><small>${x.detail}</small></div><div class="capability-track"><i style="width:${x.score*100}%;--cap:${colors[x.status]}"></i></div><span class="capability-status">${statusLabel[x.status]}</span></div>`).join('');
}

function renderBudget(){
  const b=DATA.headline.budget,max=Math.max(b.projected,b.limit),spent=Math.min(100,b.spent/max*100),limit=b.limit/max*100;
  $('#spentCost').textContent=b.spent.toFixed(4);$('#limitCost').textContent=`limit $${b.limit.toFixed(2)}`;$('#projectedCost').textContent=`projected $${b.projected.toFixed(3)}`;$('#budgetFill').style.width=`${spent}%`;$('#budgetLimit').style.left=`${limit}%`;
}

function renderTrace(){
  const t=DATA.trace;
  $('#traceMeta').innerHTML=[['RUN',t.runId],['SESSION',t.sessionId],['EVENTS',t.eventCount],['DURATION',`${t.durationMs} ms`],['STATUS',t.closed?'CLOSED':'OPEN']].map(([k,v])=>`<div><span>${k}</span><strong>${v}</strong></div>`).join('');
  const color={session:'var(--cyan)',step:'var(--cyan)',tool:'var(--purple)',system:'var(--lime)'};
  $('#traceRows').innerHTML=t.spans.map((s,i)=>`<div class="trace-row"><div class="trace-name"><strong>${s.name}</strong><small>${s.type} · ${s.status}</small></div><div class="trace-lane"><button class="span" data-span="${i}" aria-label="查看 ${s.name}" style="left:${s.start}%;width:${s.duration}%;--span:${color[s.type]}"></button></div></div>`).join('');
  $('#lifecycle').innerHTML=t.lifecycle.map(x=>`<div class="life-event">${x}</div>`).join('');
  $$('.span').forEach(btn=>btn.addEventListener('click',()=>inspectSpan(Number(btn.dataset.span),btn)));
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

function renderExperiments(rows){
  $('#experimentRows').innerHTML=rows.map(x=>`<tr><td>${x.id}</td><td>${x.time}</td><td>${x.stage}</td><td>${x.metric}</td><td><span class="status-tag ${x.status}">${statusLabel[x.status]}</span></td><td class="${x.networkCalls===0?'network-zero':''}">${x.networkCalls}</td></tr>`).join('')||'<tr><td colspan="6">没有匹配记录</td></tr>';
}

function bindUI(){
  $('#experimentSearch').addEventListener('input',e=>{const q=e.target.value.toLowerCase();renderExperiments(DATA.experiments.filter(x=>Object.values(x).join(' ').toLowerCase().includes(q)))});
  $('#focusSearch').addEventListener('click',()=>{$('#evaluations').scrollIntoView();setTimeout(()=>$('#experimentSearch').focus(),300)});
  document.addEventListener('keydown',e=>{if(e.key==='/'&&!/input|textarea/i.test(document.activeElement.tagName)){e.preventDefault();$('#focusSearch').click()}});
  $('#themeToggle').addEventListener('click',()=>{const root=document.documentElement;root.dataset.theme=root.dataset.theme==='dark'?'light':'dark'});
  $('#menuButton').addEventListener('click',()=>$('#sidebar').classList.toggle('open'));
  $$('.nav-item').forEach(a=>a.addEventListener('click',()=>{$$('.nav-item').forEach(x=>x.classList.remove('active'));a.classList.add('active');$('#sidebar').classList.remove('open')}));
  const observer=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting){$$('.nav-item').forEach(x=>x.classList.toggle('active',x.dataset.section===e.target.id))}}),{rootMargin:'-35% 0px -55% 0px'});$$('.section').forEach(s=>observer.observe(s));
}

init().catch(err=>{document.body.innerHTML=`<main style="margin:0;padding:40px"><h1>Dashboard data error</h1><pre>${err.message}</pre></main>`});
