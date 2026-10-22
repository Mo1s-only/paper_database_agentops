import type { Trace } from './types';

export interface TraceStats {
  traces: number;
  llmCalls: number;
  toolCalls: number;
  errors: number;
  tokens: number;
  cost: number;
}

export function calculateTraceStats(traces: Trace[]): TraceStats {
  return traces.reduce<TraceStats>((summary, trace) => {
    summary.traces += 1;
    summary.llmCalls += trace.spans.filter((span) => span.kind === 'llm').length;
    summary.toolCalls += trace.spans.filter((span) => span.kind === 'tool').length;
    summary.errors += trace.spans.filter((span) => span.status === 'error').length;
    summary.tokens += trace.tokens;
    summary.cost += trace.cost;
    return summary;
  }, { traces: 0, llmCalls: 0, toolCalls: 0, errors: 0, tokens: 0, cost: 0 });
}
