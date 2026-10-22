'use client';

import { Activity, AlertTriangle, Coins, Gauge, RefreshCcw, Sparkles, Workflow } from 'lucide-react';
import Link from 'next/link';
import { useMemo, useState } from 'react';
import { useDashboard } from './dashboard-context';
import { ModelUsage, TrendChart } from './charts';
import { PageHeader, StatCard, StatusBadge } from './ui';
import { calculateMetrics } from '@/lib/metrics';
import type { Trace } from '@/lib/types';
import { formatCompact, formatCost, formatDateTime, formatDuration } from '@/lib/format';

export function OverviewDashboard({ traces }: { traces: Trace[] }) {
  const { selectedProjectId, timeRange, setTimeRange } = useDashboard();
  const [refreshing, setRefreshing] = useState(false);
  const filtered = useMemo(
    () => traces.filter((trace) => selectedProjectId === 'all' || trace.projectId === selectedProjectId),
    [traces, selectedProjectId],
  );
  const metrics = useMemo(() => calculateMetrics(filtered), [filtered]);

  const refresh = () => {
    setRefreshing(true);
    window.setTimeout(() => setRefreshing(false), 650);
  };

  return (
    <>
      <PageHeader
        eyebrow="Operations / Overview"
        title="智能体运行总览"
        description="在一个视图里观察执行量、质量、延迟与模型成本。"
        actions={<><label className="select-control"><span>时间范围</span><select value={timeRange} onChange={(event) => setTimeRange(event.target.value)}><option value="24h">最近 24 小时</option><option value="7d">最近 7 天</option><option value="30d">最近 30 天</option></select></label><button className="button secondary" onClick={refresh}><RefreshCcw size={16} className={refreshing ? 'spin' : ''} />刷新</button></>}
      />

      <div className="demo-notice"><Sparkles size={16} /><span><strong>演示数据模式</strong> · 当前数据可复现，接入真实采集后自动切换为实时指标。</span><Link href="/settings">查看接入方式</Link></div>

      <section className="stats-grid" aria-label="核心指标">
        <StatCard label="Trace 总数" value={formatCompact(metrics.traceCount)} change="12.4%" icon={Activity} tone="violet" />
        <StatCard label="Span 总数" value={formatCompact(metrics.spanCount)} change="8.1%" icon={Workflow} tone="blue" />
        <StatCard label="Token 用量" value={formatCompact(metrics.totalTokens)} change="5.7%" icon={Gauge} tone="cyan" />
        <StatCard label="模型成本" value={formatCost(metrics.totalCost)} change="3.2%" icon={Coins} tone="amber" />
        <StatCard label="错误率" value={`${metrics.errorRate.toFixed(1)}%`} change="2.1%" trend="down" icon={AlertTriangle} tone="red" />
      </section>

      <section className="dashboard-grid">
        <article className="panel panel-wide">
          <div className="panel-head"><div><span className="eyebrow">Throughput</span><h2>Trace 活跃趋势</h2></div><div className="legend"><span><i className="legend-violet" />Trace</span><span><i className="legend-red" />Error</span></div></div>
          <TrendChart data={metrics.trend} />
        </article>
        <article className="panel">
          <div className="panel-head"><div><span className="eyebrow">Model mix</span><h2>模型用量与成本</h2></div></div>
          <ModelUsage data={metrics.modelUsage} />
        </article>
      </section>

      <section className="panel recent-panel">
        <div className="panel-head"><div><span className="eyebrow">Live feed</span><h2>最近执行</h2></div><Link className="text-link" href="/traces">查看全部 →</Link></div>
        <div className="table-scroll">
          <table className="data-table">
            <thead><tr><th>Trace</th><th>状态</th><th>开始时间</th><th>耗时</th><th>Tokens</th><th>成本</th></tr></thead>
            <tbody>
              {filtered.slice(0, 5).map((trace) => (
                <tr key={trace.id}>
                  <td><Link className="trace-name" href={`/traces/${trace.id}`}><span>{trace.name}</span><code>{trace.id}</code></Link></td>
                  <td><StatusBadge status={trace.status} /></td>
                  <td className="muted-cell">{formatDateTime(trace.startedAt)}</td>
                  <td>{formatDuration(trace.durationMs)}</td>
                  <td>{formatCompact(trace.tokens)}</td>
                  <td>{formatCost(trace.cost)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
