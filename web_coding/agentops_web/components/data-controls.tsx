'use client';
import { RefreshCcw, Database } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useTransition } from 'react';
import { useDashboard } from './dashboard-context';

export function DataControls() {
  const { timeRange, setTimeRange } = useDashboard();
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  return <><label className="select-control"><span>时间范围</span><select value={timeRange} onChange={(event) => setTimeRange(event.target.value)} aria-label="时间范围"><option value="1h">最近 1 小时</option><option value="24h">最近 24 小时</option><option value="7d">最近 7 天</option><option value="30d">最近 30 天</option><option value="all">全部时间</option></select></label><button className="button secondary" disabled={pending} onClick={() => startTransition(() => router.refresh())}><RefreshCcw size={16} className={pending ? 'spin' : ''} />{pending ? '刷新中' : '刷新数据'}</button></>;
}
export function DataScope() {
  const { dataMode, referenceTime, traceSource, setTraceSource } = useDashboard();
  return <div className="data-scope"><Database size={14} /><span>{dataMode === 'mock' ? '本机持久化工作区 · 含内置示例' : '远程工作区'}<i />{dataMode === 'mock' ? '时间筛选相对最新数据快照' : '查询截止时间'}：{new Date(referenceTime).toISOString().replace('T', ' ').slice(0, 16)} UTC</span>{dataMode === 'mock' && <label className="select-control source-picker"><span>数据来源</span><select aria-label="数据来源" value={traceSource} onChange={(e) => setTraceSource(e.target.value)}><option value="all">全部来源</option><option value="demo">仅示例数据</option><option value="imported">仅用户导入</option></select></label>}</div>;
}
