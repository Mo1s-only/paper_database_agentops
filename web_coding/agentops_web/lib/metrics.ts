import type { OverviewMetrics, Trace } from './types';

export function percentile(values: number[], target: number): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.ceil(target * sorted.length) - 1);
  return sorted[index];
}

export function calculateMetrics(traces: Trace[]): OverviewMetrics {
  const spans = traces.flatMap((trace) => trace.spans);
  const errors = traces.filter((trace) => trace.status === 'error').length;
  const buckets = new Map<string, { traces: number; errors: number; cost: number }>();

  for (const trace of traces) {
    const hour = `${new Date(trace.startedAt).getHours().toString().padStart(2, '0')}:00`;
    const bucket = buckets.get(hour) ?? { traces: 0, errors: 0, cost: 0 };
    bucket.traces += 1;
    bucket.errors += trace.status === 'error' ? 1 : 0;
    bucket.cost += trace.cost;
    buckets.set(hour, bucket);
  }

  const modelMap = new Map<string, { calls: number; tokens: number; cost: number }>();
  for (const span of spans.filter((item) => item.kind === 'llm')) {
    const model = span.model ?? 'unknown';
    const current = modelMap.get(model) ?? { calls: 0, tokens: 0, cost: 0 };
    current.calls += 1;
    current.tokens += span.tokens;
    current.cost += span.cost;
    modelMap.set(model, current);
  }

  return {
    traceCount: traces.length,
    spanCount: spans.length,
    totalTokens: traces.reduce((sum, trace) => sum + trace.tokens, 0),
    totalCost: traces.reduce((sum, trace) => sum + trace.cost, 0),
    errorRate: traces.length ? (errors / traces.length) * 100 : 0,
    p95LatencyMs: percentile(traces.map((trace) => trace.durationMs), 0.95),
    trend: [...buckets.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([time, value]) => ({ time, ...value })),
    modelUsage: [...modelMap.entries()]
      .map(([model, value]) => ({ model, ...value }))
      .sort((a, b) => b.tokens - a.tokens),
  };
}
