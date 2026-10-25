import type { Trace } from './types';

export const timeRanges = { '1h': 3_600_000, '24h': 86_400_000, '7d': 604_800_000, '30d': 2_592_000_000 };
export function filterTraces(traces: Trace[], projectId: string, range: string, referenceTime: number, source = 'all') {
  const duration = timeRanges[range as keyof typeof timeRanges];
  return traces.filter((trace) => {
    const started = Date.parse(trace.startedAt);
    return (projectId === 'all' || trace.projectId === projectId) && (source === 'all' || trace.provenance?.kind === source) &&
      (!duration || (started > referenceTime - duration && started <= referenceTime));
  });
}
