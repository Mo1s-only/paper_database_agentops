'use client';
import { useState } from 'react';
import { CheckCircle2, RefreshCcw, ServerCog } from 'lucide-react';
import { useDashboard } from './dashboard-context';

export function ConnectionStatus() {
  const { dataMode } = useDashboard();
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);
  async function check() {
    setChecking(true); setResult(null);
    try {
      const response = await fetch('/api/health', { cache: 'no-store', signal: AbortSignal.timeout(12000) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error?.message ?? '数据服务不可用');
      setResult({ ok: true, message: `连接成功 · ${body.projects} 个项目 · ${body.traces} 条 Trace · ${new Date(body.checkedAt).toLocaleTimeString('zh-CN')}` });
    } catch (error) { setResult({ ok: false, message: error instanceof Error ? error.message : '连接失败，请稍后重试。' }); }
    finally { setChecking(false); }
  }
  return <article className="panel connection-card"><div><span className="connection-icon"><ServerCog size={22} /></span><p><span className="eyebrow">Active connection</span><strong>{dataMode === 'mock' ? '本地 SQLite · 含内置示例' : '远程 API 数据源'}</strong><small>配置由服务端环境变量控制，浏览器不保存后端凭据。</small></p><button className="button secondary" onClick={check} disabled={checking}><RefreshCcw size={15} className={checking ? 'spin' : ''} />{checking ? '检查中' : '测试连接'}</button></div>{result && <p className={`connection-result ${result.ok ? 'ok' : 'error'}`} role="status">{result.ok && <CheckCircle2 size={15} />}{result.message}</p>}</article>;
}
