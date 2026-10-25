import type { Trace, AlertRule } from './types';
const record = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null;
const text = (v: unknown): v is string => typeof v === 'string';
const nonnegative = (v: unknown) => typeof v === 'number' && Number.isFinite(v) && v >= 0;
export function validateTraces(value: unknown): value is Trace[] {
  if (!Array.isArray(value)) return false;
  const traceIds = new Set<string>();
  return value.every((trace) => {
    if (!record(trace) || !text(trace.id) || !trace.id || traceIds.has(trace.id) || !text(trace.name) || !text(trace.projectId) || !text(trace.startedAt) || !Number.isFinite(Date.parse(trace.startedAt)) || !['ok', 'error', 'running'].includes(String(trace.status)) || ![trace.tokens, trace.cost, trace.durationMs].every(nonnegative) || !Array.isArray(trace.tags) || !trace.tags.every(text) || !Array.isArray(trace.spans)) return false;
    traceIds.add(trace.id);
    const parents = new Map<string, string | null>();
    for (const span of trace.spans) {
      if (!record(span) || !text(span.id) || !span.id || parents.has(span.id) || !(span.parentId === null || text(span.parentId)) || !['name', 'agent', 'input', 'output', 'startedAt'].every((key) => text(span[key])) || !Number.isFinite(Date.parse(span.startedAt as string)) || !['ok', 'error', 'running'].includes(String(span.status)) || !['workflow', 'agent', 'tool', 'llm'].includes(String(span.kind)) || ![span.tokens, span.cost, span.durationMs].every(nonnegative)) return false;
      parents.set(span.id, span.parentId);
    }
    // Reject missing parents and cycles before recursive tree rendering.
    for (const id of parents.keys()) {
      const seen = new Set<string>();
      let cursor: string | null = id;
      while (cursor !== null) {
        if (seen.has(cursor) || !parents.has(cursor)) return false;
        seen.add(cursor); cursor = parents.get(cursor)!;
      }
    }
    return true;
  });
}
export function validAlertRules(value: unknown): value is AlertRule[] {
  return Array.isArray(value) && value.every((r) => record(r) && text(r.id) && text(r.name) && r.name.trim().length > 0 && ['error_rate', 'latency_p95', 'daily_cost'].includes(String(r.metric)) && nonnegative(r.threshold) && (r.metric !== 'error_rate' || Number(r.threshold) <= 100) && r.operator === '>' && ['email', 'webhook'].includes(String(r.channel)) && typeof r.enabled === 'boolean');
}
