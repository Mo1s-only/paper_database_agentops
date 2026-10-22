'use client';

import { Activity, Box, Check, CheckCircle2, Clipboard, CloudCog, Cpu, ExternalLink, GitBranch, Github, HardDrive, Rocket, Server, TerminalSquare, X } from 'lucide-react';
import { useState } from 'react';
import { useDashboard } from './dashboard-context';
import { PageHeader } from './ui';

type DeployState = 'running' | 'not_deployed' | 'deploying';

export function DeployWorkspace() {
  const { projects } = useDashboard();
  const [states, setStates] = useState<Record<string, DeployState>>({ 'research-copilot': 'running' });
  const [target, setTarget] = useState<string | null>(null);
  const [branch, setBranch] = useState('main');
  const [entrypoint, setEntrypoint] = useState('src/agent.py');
  const [details, setDetails] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const detailProject = projects.find((project) => project.id === details);

  const startDeploy = () => {
    if (!target) return;
    const id = target;
    setStates((current) => ({ ...current, [id]: 'deploying' }));
    setTarget(null);
    window.setTimeout(() => setStates((current) => ({ ...current, [id]: 'running' })), 1400);
  };
  const copyEndpoint = async () => {
    await navigator.clipboard.writeText(`https://${details}.agents.example.run`);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  };

  return <>
    <PageHeader eyebrow="Runtime / Deploy" title="Agent Hosting" description="从代码仓库创建可观测的智能体运行实例；本页为本地部署流程原型。" actions={<><span className="alpha-pill">ALPHA</span><button className="button primary" onClick={() => setTarget(projects[0]?.id ?? null)}><Rocket size={16} />新建部署</button></>} />
    <div className="demo-warning"><CloudCog size={18} /><p><strong>演示模式</strong><span>操作仅更新浏览器内状态，不会连接 GitHub、启动容器或产生费用。</span></p></div>
    <section className="deploy-grid">{projects.map((project) => {
      const state = states[project.id] ?? 'not_deployed';
      return <article className="panel deploy-card" key={project.id}>
        <div className="deploy-card-head"><span className="deploy-icon"><Box size={20} /></span><span className={`deploy-state ${state}`}><i />{state === 'running' ? '运行中' : state === 'deploying' ? '部署中' : '未部署'}</span></div>
        <h2>{project.name}</h2><code>{project.id}</code>
        {state === 'running' ? <>
          <div className="runtime-metrics"><div><Activity size={15} /><span>Requests</span><strong>{project.traces24h}</strong></div><div><Server size={15} /><span>Region</span><strong>sin-1</strong></div></div>
          <div className="deploy-source"><Github size={16} /><p><span>AgentOps-AI/demo-agent</span><small><GitBranch size={12} /> {branch} · Python 3.12</small></p><button onClick={() => setDetails(project.id)} aria-label="打开部署详情"><ExternalLink size={15} /></button></div>
        </> : <div className="empty-deploy"><CloudCog size={24} /><p>{state === 'deploying' ? '正在模拟构建与启动…' : '还没有运行实例'}</p><button className="button secondary" disabled={state === 'deploying'} onClick={() => setTarget(project.id)}>{state === 'deploying' ? '部署中' : '配置部署'}</button></div>}
      </article>;
    })}</section>
    <section className="hosting-foot panel"><div><CheckCircle2 size={18} /><p><strong>可观测性默认开启</strong><span>真实部署适配器可在运行时自动注入 Trace、日志和资源指标。</span></p></div><div><CheckCircle2 size={18} /><p><strong>适合渐进扩容</strong><span>前端保持无状态，运行层可从单机容器迁移到 Kubernetes。</span></p></div></section>

    {target && <div className="dialog-backdrop" onMouseDown={() => setTarget(null)}><section className="modal-card deploy-modal" onMouseDown={(event) => event.stopPropagation()} role="dialog" aria-modal="true"><div className="modal-head"><div><span className="eyebrow">Demo deploy</span><h2>配置运行实例</h2></div><button className="icon-button" onClick={() => setTarget(null)}><X size={18} /></button></div><label className="field"><span>项目</span><select value={target} onChange={(event) => setTarget(event.target.value)}>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label><label className="field"><span>Git 仓库</span><input value="AgentOps-AI/demo-agent" readOnly /></label><div className="two-fields"><label className="field"><span>分支</span><input value={branch} onChange={(event) => setBranch(event.target.value)} /></label><label className="field"><span>区域</span><select defaultValue="sin-1"><option value="sin-1">Singapore</option><option value="hkg-1">Hong Kong</option></select></label></div><label className="field"><span>入口文件</span><input value={entrypoint} onChange={(event) => setEntrypoint(event.target.value)} /></label><p className="form-note">这是交互原型：确认后只会模拟部署状态，不会访问外部仓库。</p><div className="modal-actions"><button className="button secondary" onClick={() => setTarget(null)}>取消</button><button className="button primary" onClick={startDeploy}><Rocket size={15} />开始模拟部署</button></div></section></div>}

    {details && detailProject && <><button className="drawer-scrim" onClick={() => setDetails(null)} aria-label="关闭部署详情" /><aside className="deploy-details-drawer" role="dialog" aria-modal="true" aria-label="部署详情"><div className="drawer-head"><div><span className="eyebrow">Runtime instance</span><h2>{detailProject.name}</h2><code>dep_{detailProject.id.replaceAll('-', '_')}</code></div><button className="icon-button" onClick={() => setDetails(null)} aria-label="关闭"><X size={18} /></button></div><div className="deployment-health"><span className="deploy-state running"><i />运行正常</span><small>最近检查：刚刚</small></div><section className="endpoint-card"><span>HTTPS ENDPOINT</span><div><code>https://{details}.agents.example.run</code><button onClick={copyEndpoint}>{copied ? <Check size={14} /> : <Clipboard size={14} />}{copied ? '已复制' : '复制'}</button></div><p>演示地址，不会向公网发起请求。</p></section><section className="runtime-stat-grid"><div><Cpu size={16} /><span>CPU</span><strong>7%</strong></div><div><HardDrive size={16} /><span>Memory</span><strong>186 MB</strong></div><div><Activity size={16} /><span>Requests</span><strong>{detailProject.traces24h}</strong></div><div><Server size={16} /><span>Region</span><strong>sin-1</strong></div></section><section className="build-info"><div className="drawer-section-head"><div><span className="eyebrow">Build</span><h3>构建信息</h3></div><span>成功</span></div><dl><div><dt>Repository</dt><dd>AgentOps-AI/demo-agent</dd></div><div><dt>Revision</dt><dd><code>7ac48e1</code></dd></div><div><dt>Branch</dt><dd>{branch}</dd></div><div><dt>Runtime</dt><dd>Python 3.12</dd></div><div><dt>Entrypoint</dt><dd><code>{entrypoint}</code></dd></div></dl></section><section className="runtime-logs"><div className="drawer-section-head"><div><span className="eyebrow">Runtime logs</span><h3>最近日志</h3></div><TerminalSquare size={16} /></div><pre><span>12:04:18</span> INFO  instance boot completed{`\n`}<span>12:04:19</span> INFO  AgentOps instrumentation enabled{`\n`}<span>12:06:42</span> INFO  POST /run 200 1842ms{`\n`}<span>12:08:03</span> INFO  trace exported successfully</pre></section></aside></>}
  </>;
}
