'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Database, FileJson, History, RefreshCcw, ShieldCheck } from 'lucide-react';
import { PageHeader } from './ui';
import { ConnectionStatus } from './connection-status';
import { useDashboard } from './dashboard-context';

type AuditEvent = { id: number; action: string; entity: string; createdAt: string };
const actionNames: Record<string, string> = { 'project.saved': '项目已保存', 'alerts.saved': '告警策略已保存', 'traces.imported': 'Trace 批次已导入', 'label.saved': '人工标签已保存' };

export function SettingsWorkspace() {
  const { dataMode } = useDashboard();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  async function refreshAudit() {
    setLoading(true); setError('');
    try {
      const response = await fetch('/api/v1/audit', { cache: 'no-store', signal: AbortSignal.timeout(12000) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error?.message ?? '操作记录加载失败');
      setEvents(body.data);
    } catch (error) { setError(error instanceof Error ? error.message : '操作记录加载失败'); }
    finally { setLoading(false); }
  }
  useEffect(() => { if (dataMode === 'mock') void refreshAudit(); }, [dataMode]);
  return <>
    <PageHeader eyebrow="Workspace / Settings" title="设置与接入" description="查看真实连接、数据持久化和当前系统的能力边界。" />
    <ConnectionStatus />
    <section className="settings-grid">
      <article className="panel settings-panel"><div className="panel-head"><div><span className="eyebrow">Storage</span><h2>{dataMode === 'mock' ? '本机 SQLite 存储' : '远程只读 API'}</h2></div><Database size={20} /></div>
        <div className="settings-copy"><p>{dataMode === 'mock' ? '项目、告警配置、导入 Trace 与人工标签保存到服务端数据库。同一服务地址更换浏览器也能读取；内置示例仅供功能演示。' : '服务端从配置的 API 获取数据。写入由远程后端管理，当前控制台不提供远程配置变更。'}</p>
          <dl><div><dt>当前模式</dt><dd><code>AGENTOPS_DATA_MODE={dataMode}</code></dd></div><div><dt>默认数据库</dt><dd><code>.data/agentops.sqlite</code></dd></div><div><dt>可选路径配置</dt><dd><code>AGENTOPS_DB_PATH</code></dd></div><div><dt>运行环境</dt><dd>Node.js 24+ · 单实例本地部署</dd></div></dl>
          <p>备份前先正常停止服务，再复制整个 <code>.data</code> 目录（包含 WAL 文件）。不要把数据库、日志或凭据提交到 Git。容器重建前需配置持久化卷。</p>
        </div>
      </article>
      <article className="panel settings-panel"><div className="panel-head"><div><span className="eyebrow">Access boundary</span><h2>访问与上线边界</h2></div><ShieldCheck size={20} /></div>
        <div className="settings-copy"><p>本地启动脚本绑定 <code>127.0.0.1</code>。写入校验同源、回环 Host 和请求标头，远程数据模式禁用写入。</p><p>这不是用户身份认证。当前没有登录、租户隔离、真实 API Key、告警调度或通知投递；请勿直接暴露到公网。</p><p>正式上线需增加身份认证与权限校验、租户数据隔离、部署级网络限制和备份恢复方案。当前版本未进行生产负载或安全验收。</p></div>
      </article>
    </section>
    <section className="panel sdk-panel"><div className="panel-head"><div><span className="eyebrow">Data onboarding</span><h2>接入你的 Trace 数据</h2></div><FileJson size={20} /></div><div className="settings-copy">
      <ol><li>在“项目管理”创建项目，为不同应用或实验设置独立归属。</li><li>将采集结果转换为本项目的 Trace JSON：每条执行包含唯一 ID、时间、状态、成本、Tokens 和 Span 父子关系。</li><li>进入 Trace 探索器，选择“导入 Trace”。上传或粘贴 JSON，选择目标项目，先校验再确认导入。</li><li>进入详情查看执行树与输入输出；失败记录可添加人工根因标签，在评测页对照和导出。</li></ol>
      <p>支持数组、<code>{'{ traces: [...] }'}</code> 和 <code>{'{ data: [...] }'}</code>。单批最多 5 MiB / 100 Traces / 2000 Spans。重复 ID 整批拒绝；示例文件始终保留演示来源标记。用户导入仅表示输入渠道，不表示数据真实性已验证。</p>
      <p>此 JSON 契约不是官方 AgentOps SDK 或 OTLP 协议，不能将 SDK endpoint 直接指向本控制台。</p>
      <div className="settings-actions"><Link href="/traces" className="button primary">打开 Trace 导入</Link><a href="/examples/trace-import.json" download className="button secondary">下载结构示例</a></div>
    </div></section>
    {dataMode === 'mock' && <section className="panel audit-panel"><div className="panel-head"><div><span className="eyebrow">Local operation history</span><h2>最近操作记录</h2></div><button className="button secondary" onClick={refreshAudit} disabled={loading}><RefreshCcw size={15} className={loading ? 'spin' : ''} />刷新记录</button></div>
      <p className="policy-note">最近 100 条本机操作；不含输入 / 输出正文。当前无用户身份与防篡改机制，不是合规审计系统。</p>
      {error ? <p className="form-error" role="alert">{error}</p> : events.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th>操作</th><th>对象 ID</th><th>时间（UTC）</th></tr></thead><tbody>{events.map((event) => <tr key={event.id}><td>{actionNames[event.action] ?? event.action}</td><td><code>{event.entity}</code></td><td>{event.createdAt.replace('T', ' ').slice(0, 19)}</td></tr>)}</tbody></table></div> : <p className="audit-empty"><History size={18} />{loading ? '正在加载…' : '暂无操作。保存项目、策略、标签或导入数据后会在这里留痕。'}</p>}
    </section>}
  </>;
}
