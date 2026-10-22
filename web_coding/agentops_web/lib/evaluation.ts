import { attributeFailure } from './attribution';
import type { FailureAttribution, GroundTruthLabel, Trace } from './types';

export interface EvaluationRecord {
  trace: Trace;
  attribution: FailureAttribution;
  groundTruth: GroundTruthLabel | null;
  agreesWithHuman: boolean | null;
}

export function buildEvaluationRecords(traces: Trace[], labels: GroundTruthLabel[]): EvaluationRecord[] {
  const labelsByTrace = new Map(labels.map((label) => [label.traceId, label]));

  return traces
    .filter((trace) => trace.status === 'error')
    .map((trace) => {
      const attribution = attributeFailure(trace);
      const groundTruth = labelsByTrace.get(trace.id) ?? null;
      return {
        trace,
        attribution,
        groundTruth,
        agreesWithHuman: groundTruth && attribution.rootSpanId
          ? groundTruth.rootSpanId === attribution.rootSpanId
          : null,
      };
    });
}
