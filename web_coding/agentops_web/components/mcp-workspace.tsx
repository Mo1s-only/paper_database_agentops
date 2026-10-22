'use client';

import { Check, Clipboard, Code2, Database, FileJson, PlugZap, Search, Server, Workflow } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useDashboard } from './dashboard-context';
import { PageHeader } from './ui';

type Client = 'cursor' | 'claude' | 'vscode';

const tools = [
  { name: 'get_trace', description: '按 Trace ID 获取摘要、状态与顶层属性。', icon: Search },
  { name: 'get_span', description: '读取单个 Span 的输入、输出、错误和时间信息。', icon: FileJson },
  { name: 'get_complete_trace', description: '返回完整调用树，适合故障复盘与因果分析。', icon: Workflow },
  { name: 'search_traces', description: '按项目、状态、标签和时间范围检索执行记录。', icon: Database },
  { name: 'get_metrics', description: '聚合调用量、错误率、延迟、Token 与成本指标。', icon: Server },
];

export function McpWorkspace() {
  const { projects, selectedProjectId } = useDashboard();
  const [client, setClient] = useState<Client>('cursor');
  const [copied, setCopied] = useState(false);
  const project = projects.find((item) => item.id === selectedProjectId) ?? projects[0];
  const config = useMemo(() => {
    const base = {
      command: 'npx',
      args: ['-y', '@agentops/mcp-server'],
      env: { AGENTOPS_API_KEY: 'YOUR_SERVER_SIDE_API_KEY', AGENTOPS_PROJECT_ID: project?.id ?? 'YOUR_PROJECT_ID' },
    };
    if (client === 'vscode') return JSON.stringify({ servers: { agentops: { type: 'stdio', ...base } } }, null, 2);
    return JSON.stringify({ mcpServers: { agentops: base } }, null, 2);
  }, [client, project?.id]);
  const copy = async () => {
    await navigator.clipboard.writeText(config);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  };

  return <>
    <PageHeader eyebrow="Integrations / MCP" title="MCP Server" description="让 IDE 与智能体直接检索 Trace、Span 和聚合指标；当前页面提供安全的配置模板。" actions={<span className="preview-pill"><i />配置预览</span>} />
    <section className="mcp-hero panel">
      <div className="mcp-hero-copy"><span className="mcp-mark"><PlugZap size={25} /></span><div><span className="eyebrow">Model Context Protocol</span><h2>把可观测性上下文带进调试工作流</h2><p>选择客户端并复制配置。真实接入时仅在本机或服务端注入 API Key，不要将密钥提交到仓库。</p></div></div>
      <div className="mcp-project"><span>当前项目</span><strong>{project?.name ?? '未选择项目'}</strong><code>{project?.id ?? '—'}</code></div>
    </section>

    <section className="mcp-layout">
      <article className="panel mcp-setup">
        <div className="panel-head"><div><span className="eyebrow">Setup</span><h2>客户端配置</h2></div><Code2 size={19} /></div>
        <div className="client-tabs">{(['cursor', 'claude', 'vscode'] as Client[]).map((item) => <button key={item} className={client === item ? 'active' : ''} onClick={() => setClient(item)}>{item === 'claude' ? 'Claude Desktop' : item === 'vscode' ? 'VS Code' : 'Cursor'}</button>)}</div>
        <div className="mcp-code"><div><span>{client}.json</span><button onClick={copy}>{copied ? <Check size={15} /> : <Clipboard size={15} />}{copied ? '已复制' : '复制配置'}</button></div><pre><code>{config}</code></pre></div>
        <div className="safe-callout"><strong>密钥占位符</strong><span>模板故意使用 <code>YOUR_SERVER_SIDE_API_KEY</code>，页面不会读取或输出真实凭据。</span></div>
      </article>

      <article className="panel mcp-tools">
        <div className="panel-head"><div><span className="eyebrow">Capabilities</span><h2>可用工具</h2></div><span className="tool-count">{tools.length} tools</span></div>
        <div className="mcp-tool-list">{tools.map((tool) => { const Icon = tool.icon; return <div key={tool.name}><span><Icon size={17} /></span><p><code>{tool.name}</code><small>{tool.description}</small></p><i>read</i></div>; })}</div>
      </article>
    </section>
  </>;
}
