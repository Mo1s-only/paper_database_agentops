import { describe, expect, it } from 'vitest';
import { attributeFailure } from './attribution';
import { traces } from './mock-data';

describe('transparent attribution baseline', () => {
  it('ranks the failed tool call as the primary suspect and preserves its path', () => {
    const result = attributeFailure(traces.find((trace) => trace.status === 'error')!);
    expect(result.rootSpanId).toBe('sp_b6');
    expect(result.propagationPath).toEqual(['sp_b1', 'sp_b4', 'sp_b6']);
    expect(result.status).toBe('demo_heuristic');
  });

  it('does not attribute a successful trace', () => {
    const result = attributeFailure(traces.find((trace) => trace.status === 'ok')!);
    expect(result.rootSpanId).toBeNull();
    expect(result.status).toBe('no_failure');
  });
});
