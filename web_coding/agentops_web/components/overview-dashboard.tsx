'use client';

import { Activity, AlertTriangle, Coins, Gauge, RefreshCcw, Sparkles, Workflow } from 'lucide-react';
import Link from 'next/link';
import { useMemo } from 'react';
import { filterTraces } from '@/lib/query';
import { DataControls, DataScope } from './data-controls';
import { useDashboard } from './dashboard-context';
import { ModelUsage, TrendChart } from './charts';
import { PageHeader, StatCard, StatusBadge } from './ui';
import { calculateMetrics } from '@/lib/metrics';
import type { Trace } from '@/lib/types';
import { formatCompact, formatCost, formatDateTime, formatDuration } from '@/lib/format';

export function OverviewDashboard({ traces }: { traces: Trace[] }) {
  const { selectedProjectId, timeRange, referenceTime, traceSource } = useDashboard();
  const filtered = useMemo(
    () => filterTraces(traces, selectedProjectId, timeRange, referenceTime, traceSource).sort((a, b) => Date.parse(b.startedAt) - Date.parse(a.startedAt)),
    [traces, selectedProjectId, timeRange, referenceTime, traceSource],
  );
  const metrics = useMemo(() => calculateMetrics(filtered), [filtered]);

  return (
    <>
      <PageHeader
        eyebrow="Operations / Overview"
        title="智能体运行总览"
        description="在一个视图里观察执行量、质量、延迟与模型成本。"
        actions={<DataControls />}
      />

      <DataScope />

      <section className="stats-grid" aria-label="核心指标">
        <StatCard label="Trace 总数" value={formatCompact(metrics.traceCount)} icon={Activity} tone="violet" />
        <StatCard label="Span 总数" value={formatCompact(metrics.spanCount)} icon={Workflow} tone="blue" />
        <StatCard label="Token 用量" value={formatCompact(metrics.totalTokens)} icon={Gauge} tone="cyan" />
        <StatCard label="模型成本" value={formatCost(metrics.totalCost)} icon={Coins} tone="amber" />
        <StatCard label="错误率" value={filtered.length ? `${metrics.errorRate.toFixed(1)}%` : '—'} icon={AlertTriangle} tone="red" />
      </section>

      <section className="operations-strip" aria-label="运行洞察">
        <div><span className="eyebrow">Operational pulse</span><h2>需要关注的执行</h2><p>从当前范围直接定位失败与高延迟。</p></div>
        <Link href="/traces?status=error"><AlertTriangle size={19} /><span><strong>{filtered.filter((t) => t.status === 'error').length}</strong> 失败 Trace<small>打开失败队列 →</small></span></Link>
        <Link href="/metrics"><Gauge size={19} /><span><strong>{filtered.length ? formatDuration(metrics.p95LatencyMs) : '—'}</strong> P95 延迟<small>查看性能分布 →</small></span></Link>
        <Link href="/settings"><Sparkles size={19} /><span><strong>连接数据源</strong><small>检查接口与工作区状态 →</small></span></Link>
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
              {!filtered.length && <tr><td colSpan={6}><div className="empty-compact">此时间范围没有执行记录，请扩大时间范围或切换项目。</div></td></tr>}
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
