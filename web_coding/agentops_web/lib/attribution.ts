import type { AttributionEvidence, FailureAttribution, Span, Trace } from './types';

function spanScore(span: Span, trace: Trace): number {
  const errorSignal = span.status === 'error' ? 0.58 : 0;
  const explicitError = span.error ? 0.12 : 0;
  const kindSignal = span.kind === 'tool' ? 0.15 : span.kind === 'llm' ? 0.07 : 0;
  const latencySignal = Math.min(0.15, (span.durationMs / Math.max(trace.durationMs, 1)) * 0.15);
  return Math.min(0.98, errorSignal + explicitError + kindSignal + latencySignal);
}

function propagationPath(spans: Span[], targetId: string): string[] {
  const byId = new Map(spans.map((span) => [span.id, span]));
  const path: string[] = [];
  let current = byId.get(targetId);
  while (current) {
    path.unshift(current.id);
    current = current.parentId ? byId.get(current.parentId) : undefined;
  }
  return path;
}

export function attributeFailure(trace: Trace): FailureAttribution {
  const failed = trace.spans.filter((span) => span.status === 'error');
  if (!failed.length) {
    return { traceId: trace.id, method: 'transparent-rule-baseline', methodVersion: '0.1.0', rootSpanId: null, score: null, propagationPath: [], evidence: [], status: 'no_failure' };
  }

  const ranked = failed
    .map((span) => ({ span, score: spanScore(span, trace) }))
    .sort((a, b) => b.score - a.score);
  const root = ranked[0];
  const evidence: AttributionEvidence[] = ranked.map(({ span, score }) => ({
    spanId: span.id,
    signal: span.kind === 'tool' ? 'tool' : span.error ? 'error' : 'latency',
    observation: span.error ?? `${span.kind} span 以 error 状态结束，耗时 ${span.durationMs}ms。`,
    score,
  }));

  return {
    traceId: trace.id,
    method: 'transparent-rule-baseline',
    methodVersion: '0.1.0',
    rootSpanId: root.span.id,
    score: root.score,
    propagationPath: propagationPath(trace.spans, root.span.id),
    evidence,
    status: 'demo_heuristic',
  };
}
