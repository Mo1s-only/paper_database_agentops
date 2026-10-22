import { describe, expect, it } from 'vitest';
import { calculateMetrics, percentile } from './metrics';
import { traces } from './mock-data';

describe('metrics', () => {
  it('uses nearest-rank percentile semantics', () => {
    expect(percentile([10, 20, 30, 40], 0.95)).toBe(40);
    expect(percentile([], 0.95)).toBe(0);
  });

  it('aggregates trace, span, error and model data', () => {
    const metrics = calculateMetrics(traces);
    expect(metrics.traceCount).toBe(traces.length);
    expect(metrics.spanCount).toBe(traces.flatMap((trace) => trace.spans).length);
    expect(metrics.errorRate).toBeCloseTo(100 / traces.length);
    expect(metrics.modelUsage.length).toBeGreaterThan(1);
  });
});
