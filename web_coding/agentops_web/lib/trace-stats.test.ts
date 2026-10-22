import { describe, expect, it } from 'vitest';
import { traces } from './mock-data';
import { calculateTraceStats } from './trace-stats';

describe('trace summary', () => {
  it('classifies LLM, tool and error spans without double-counting traces', () => {
    const summary = calculateTraceStats(traces.slice(0, 2));
    expect(summary.traces).toBe(2);
    expect(summary.llmCalls).toBe(5);
    expect(summary.toolCalls).toBe(3);
    expect(summary.errors).toBe(3);
    expect(summary.tokens).toBe(28_248);
  });
});
