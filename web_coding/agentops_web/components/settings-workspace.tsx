'use client';

import { Check, Clipboard, ExternalLink, KeyRound, Plus, PlugZap, ServerCog, ShieldCheck, Trash2, X } from 'lucide-react';
import { useState } from 'react';
import { PageHeader } from './ui';

const snippets = {
  python: `pip install agentops

import agentops

agentops.init(
    api_key=os.environ["AGENTOPS_API_KEY"],
    endpoint=os.environ.get("AGENTOPS_ENDPOINT")
)

# your agent workflow
agentops.end_session("Success")`,
  typescript: `npm install agentops @openai/agents

import AgentOps from "agentops";

const agentops = new AgentOps({
  apiKey: process.env.AGENTOPS_API_KEY!,
  endpoint: process.env.AGENTOPS_ENDPOINT,
});

await agentops.startSession();`,
  otel: `export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_SERVICE_NAME=my-agent-service`,
};

export function SettingsWorkspace() {
  const [language, setLanguage] = useState<keyof typeof snippets>('python');
  const [copied, setCopied] = useState(false);
  const [mode, setMode] = useState('mock');
  const [keys, setKeys] = useState([
    { id: 'key-1', name: 'Production ingest', hint: 'aop_••••7F2A', scope: 'ingest + read', used: '8 分钟前' },
    { id: 'key-2', name: 'Local development', hint: 'aop_••••3B80', scope: 'read', used: '2 天前' },
  ]);
  const [keyDialog, setKeyDialog] = useState(false);
  const [keyName, setKeyName] = useState('Thesis experiment');
  const [createdKey, setCreatedKey] = useState('');
  const copy = async () => { await navigator.clipboard.writeText(snippets[language]); setCopied(true); window.setTimeout(() => setCopied(false), 1200); };
  const createDemoKey = () => {
    const suffix = crypto.randomUUID().replaceAll('-', '').slice(0, 20);
    const token = `aop_demo_${suffix}`;
    setKeys((current) => [...current, { id: crypto.randomUUID(), name: keyName || 'Untitled key', hint: `aop_••••${suffix.slice(-4).toUpperCase()}`, scope: 'read', used: '尚未使用' }]);
    setCreatedKey(token);
  };
  const closeKeyDialog = () => { setKeyDialog(false); setCreatedKey(''); setKeyName('Thesis experiment'); };

  return <>
    <PageHeader eyebrow="Workspace / Settings" title="设置与接入" description="配置数据源、SDK 和部署边界。" />
    <section className="settings-grid">
      <article className="panel settings-panel">
        <div className="panel-head"><div><span className="eyebrow">Data source</span><h2>数据源模式</h2></div><ServerCog size={20} /></div>
        <div className="mode-options">
          <button className={mode === 'mock' ? 'active' : ''} onClick={() => setMode('mock')}><span><PlugZap size={18} /></span><div><strong>演示数据</strong><small>内置、确定性数据集，适合 UI 开发和答辩演示。</small></div><i /></button>
          <button className={mode === 'remote' ? 'active' : ''} onClick={() => setMode('remote')}><span><ServerCog size={18} /></span><div><strong>远程 API</strong><small>连接 FastAPI / ClickHouse 服务，适合正式环境。</small></div><i /></button>
        </div>
        <div className="config-preview"><span>环境变量</span><code>AGENTOPS_DATA_MODE={mode}</code>{mode === 'remote' && <code>AGENTOPS_API_URL=https://api.example.com</code>}</div>
      </article>

      <article className="panel settings-panel">
        <div className="panel-head"><div><span className="eyebrow">Security</span><h2>密钥与访问</h2></div><ShieldCheck size={20} /></div>
        <div className="security-list"><div><KeyRound size={18} /><p><strong>服务端密钥</strong><span>只通过环境变量读取，不暴露到浏览器 bundle。</span></p><span className="status status-ok"><i />安全</span></div><div><ShieldCheck size={18} /><p><strong>API 边界</strong><span>前端只访问同源 Route Handler，可替换为鉴权网关。</span></p><span className="status status-ok"><i />就绪</span></div></div>
      </article>
    </section>

    <section className="panel api-key-panel">
      <div className="panel-head"><div><span className="eyebrow">API Keys</span><h2>访问密钥</h2></div><button className="button secondary" onClick={() => setKeyDialog(true)}><Plus size={15} />生成演示密钥</button></div>
      <div className="key-table-head"><span>名称</span><span>Key</span><span>权限</span><span>最近使用</span><span /></div>
      <div className="api-key-list">{keys.map((key) => <div key={key.id}><p><strong>{key.name}</strong><small>仅服务端使用</small></p><code>{key.hint}</code><span>{key.scope}</span><span>{key.used}</span><button onClick={() => setKeys((current) => current.filter((item) => item.id !== key.id))} aria-label={`删除 ${key.name}`}><Trash2 size={15} /></button></div>)}</div>
      <div className="api-key-foot"><ShieldCheck size={16} /><span>列表仅保存演示元数据；真实密钥应由后端加密存储，并在生成后只展示一次。</span></div>
    </section>

    <section className="panel sdk-panel">
      <div className="panel-head"><div><span className="eyebrow">Instrumentation</span><h2>接入你的智能体</h2></div><a className="text-link" href="https://docs.agentops.ai" target="_blank" rel="noreferrer">官方文档 <ExternalLink size={14} /></a></div>
      <div className="sdk-layout">
        <div className="sdk-steps"><div className="active"><i>1</i><p><strong>安装采集 SDK</strong><span>选择现有框架对应的接入方式。</span></p></div><div><i>2</i><p><strong>配置环境变量</strong><span>API Key 与 endpoint 只放在服务端。</span></p></div><div><i>3</i><p><strong>运行一次工作流</strong><span>新的 Trace 会出现在探索器中。</span></p></div></div>
        <div className="code-card"><div className="code-tabs">{(Object.keys(snippets) as Array<keyof typeof snippets>).map((item) => <button key={item} className={language === item ? 'active' : ''} onClick={() => setLanguage(item)}>{item === 'otel' ? 'OpenTelemetry' : item}</button>)}<button className="copy-code" onClick={copy}>{copied ? <Check size={15} /> : <Clipboard size={15} />}{copied ? '已复制' : '复制'}</button></div><pre><code>{snippets[language]}</code></pre></div>
      </div>
    </section>

    {keyDialog && <div className="dialog-backdrop" onMouseDown={closeKeyDialog}><section className="modal-card" onMouseDown={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-label="生成演示密钥"><div className="modal-head"><div><span className="eyebrow">Local demo only</span><h2>{createdKey ? '复制演示密钥' : '新建 API Key'}</h2></div><button className="icon-button" onClick={closeKeyDialog}><X size={18} /></button></div>{createdKey ? <><div className="created-key"><code>{createdKey}</code><button onClick={() => navigator.clipboard.writeText(createdKey)}><Clipboard size={16} />复制</button></div><p className="form-note">只会显示这一次。该值仅用于 UI 演示，不能连接任何真实服务。</p><div className="modal-actions"><button className="button primary" onClick={closeKeyDialog}>完成</button></div></> : <><label className="field"><span>密钥名称</span><input value={keyName} onChange={(event) => setKeyName(event.target.value)} /></label><label className="field"><span>权限</span><select defaultValue="read"><option value="read">只读</option><option value="ingest">写入 Trace</option><option value="admin">管理</option></select></label><p className="form-note">生成动作仅更新当前浏览器内存，不会创建真实凭据。</p><div className="modal-actions"><button className="button secondary" onClick={closeKeyDialog}>取消</button><button className="button primary" onClick={createDemoKey}><KeyRound size={15} />生成演示密钥</button></div></>}</section></div>}
  </>;
}
