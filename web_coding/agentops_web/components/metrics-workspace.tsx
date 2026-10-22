'use client';

import { Activity, AlertTriangle, Bot, Coins, Gauge, Timer, Wrench } from 'lucide-react';
import { useMemo } from 'react';
import { TrendChart } from './charts';
import { useDashboard } from './dashboard-context';
import { PageHeader } from './ui';
import { formatCompact, formatCost, formatDuration } from '@/lib/format';
import { calculateMetrics } from '@/lib/metrics';
import type { Trace } from '@/lib/types';

export function MetricsWorkspace({ traces }: { traces: Trace[] }) {
  const { selectedProjectId, timeRange, setTimeRange } = useDashboard();
  const filtered = useMemo(() => traces.filter((trace) => selectedProjectId === 'all' || trace.projectId === selectedProjectId), [traces, selectedProjectId]);
  const metrics = useMemo(() => calculateMetrics(filtered), [filtered]);
  const callMix = useMemo(() => {
    const spans = filtered.flatMap((trace) => trace.spans);
    return [
      { label: 'Agent', value: spans.filter((span) => span.kind === 'agent').length, icon: Bot, tone: 'cyan' },
      { label: 'LLM', value: spans.filter((span) => span.kind === 'llm').length, icon: Activity, tone: 'blue' },
      { label: 'Tool', value: spans.filter((span) => span.kind === 'tool').length, icon: Wrench, tone: 'amber' },
    ];
  }, [filtered]);
  const maxLatency = Math.max(...filtered.map((trace) => trace.durationMs), 1);

  return <>
    <PageHeader eyebrow="Analytics / Metrics" title="性能与成本指标" description="按项目查看吞吐、延迟、错误、模型和调用类型分布。" actions={<label className="select-control"><span>时间范围</span><select value={timeRange} onChange={(event) => setTimeRange(event.target.value)}><option value="24h">最近 24 小时</option><option value="7d">最近 7 天</option><option value="30d">最近 30 天</option></select></label>} />
    <div className="metrics-note"><Gauge size={17} /><span><strong>确定性演示数据</strong> · 时间范围控件已保留接口，接入真实后端后由查询参数驱动聚合。</span></div>
    <section className="metrics-kpis">
      <article><span className="tone-violet"><Activity size={18} /></span><p><small>Trace 数</small><strong>{formatCompact(metrics.traceCount)}</strong><em>当前筛选</em></p></article>
      <article><span className="tone-blue"><Timer size={18} /></span><p><small>P95 延迟</small><strong>{formatDuration(metrics.p95LatencyMs)}</strong><em>nearest-rank</em></p></article>
      <article><span className="tone-red"><AlertTriangle size={18} /></span><p><small>错误率</small><strong>{metrics.errorRate.toFixed(1)}%</strong><em>{filtered.filter((trace) => trace.status === 'error').length} failed traces</em></p></article>
      <article><span className="tone-amber"><Coins size={18} /></span><p><small>模型成本</small><strong>{formatCost(metrics.totalCost)}</strong><em>{formatCompact(metrics.totalTokens)} tokens</em></p></article>
    </section>
    <section className="metrics-layout">
      <article className="panel metrics-trend"><div className="panel-head"><div><span className="eyebrow">Volume</span><h2>执行量趋势</h2></div><div className="legend"><span><i className="legend-violet" />Trace</span></div></div><TrendChart data={metrics.trend} /></article>
      <article className="panel call-mix-panel"><div className="panel-head"><div><span className="eyebrow">Span mix</span><h2>调用类型</h2></div></div><div className="call-mix">{callMix.map((item) => { const Icon = item.icon; const total = Math.max(1, callMix.reduce((sum, candidate) => sum + candidate.value, 0)); return <div key={item.label}><span className={`tone-${item.tone}`}><Icon size={16} /></span><p><strong>{item.label}</strong><small>{item.value} calls</small></p><div><i style={{ width: `${item.value / total * 100}%` }} /></div><b>{(item.value / total * 100).toFixed(0)}%</b></div>; })}</div></article>
    </section>
    <section className="metrics-bottom-grid">
      <article className="panel latency-panel"><div className="panel-head"><div><span className="eyebrow">Latency</span><h2>Trace 延迟排行</h2></div></div><div className="latency-list">{[...filtered].sort((a, b) => b.durationMs - a.durationMs).map((trace) => <div key={trace.id}><p><strong>{trace.name}</strong><code>{trace.id}</code></p><div><i className={trace.status === 'error' ? 'error' : ''} style={{ width: `${trace.durationMs / maxLatency * 100}%` }} /></div><span>{formatDuration(trace.durationMs)}</span></div>)}</div></article>
      <article className="panel model-cost-panel"><div className="panel-head"><div><span className="eyebrow">Models</span><h2>模型成本明细</h2></div></div><div className="model-metric-head"><span>模型</span><span>调用</span><span>Tokens</span><span>成本</span></div>{metrics.modelUsage.map((model) => <div className="model-metric-row" key={model.model}><strong>{model.model}</strong><span>{model.calls}</span><span>{formatCompact(model.tokens)}</span><span>{formatCost(model.cost)}</span></div>)}</article>
    </section>
  </>;
}
