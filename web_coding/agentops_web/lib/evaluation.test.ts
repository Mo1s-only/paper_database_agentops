import { describe, expect, it } from 'vitest';
import { traces } from './mock-data';
import { buildEvaluationRecords } from './evaluation';
import type { GroundTruthLabel } from './types';

const failedTrace = traces.find((trace) => trace.status === 'error')!;

function label(rootSpanId: string): GroundTruthLabel {
  return {
    traceId: failedTrace.id,
    rootSpanId,
    failureType: 'tool_failure',
    note: 'Test fixture label',
    createdAt: '2026-10-20T00:00:00.000Z',
  };
}

describe('buildEvaluationRecords', () => {
  it('keeps agreement unknown until a human label exists', () => {
    const [record] = buildEvaluationRecords(traces, []);
    expect(record.groundTruth).toBeNull();
    expect(record.agreesWithHuman).toBeNull();
  });

  it('compares the baseline candidate with the human root span', () => {
    expect(buildEvaluationRecords(traces, [label('sp_b6')])[0].agreesWithHuman).toBe(true);
    expect(buildEvaluationRecords(traces, [label('sp_b7')])[0].agreesWithHuman).toBe(false);
  });
});
