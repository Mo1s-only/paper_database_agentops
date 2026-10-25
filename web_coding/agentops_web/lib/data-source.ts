import { alertRules, projects, traces } from './mock-data';
import { calculateMetrics } from './metrics';
import { fetchUpstream, UpstreamError } from './upstream';
import { validateTraces, validAlertRules } from './validation';
import { getLocalStore } from './local-store';

export type DataMode = 'mock' | 'remote';

export function getDataMode(): DataMode {
  return process.env.AGENTOPS_DATA_MODE === 'remote' ? 'remote' : 'mock';
}

async function remoteGet<T>(path: string): Promise<T> {
  return fetchUpstream<T>(process.env.AGENTOPS_API_URL, path, process.env.AGENTOPS_API_TOKEN);
}

export function getReferenceTime() {
  return getDataMode() === 'mock' ? Math.max(...getLocalStore().traces().map((t) => Date.parse(t.startedAt))) : Date.now();
}

export async function getProjects() {
  const result = getDataMode() === 'remote' ? await remoteGet<typeof projects>('/v1/projects') : getLocalStore().projects();
  if (!Array.isArray(result) || !result.every((p) => p && typeof p.id === 'string' && typeof p.name === 'string' && ['development', 'staging', 'production'].includes(p.environment))) throw new UpstreamError('INVALID_RESPONSE');
  return result;
}

export async function getTraces() {
  const result = getDataMode() === 'remote' ? await remoteGet<unknown>('/v1/traces') : getLocalStore().traces();
  if (!validateTraces(result)) throw new UpstreamError('INVALID_RESPONSE');
  return result;
}

export async function getTrace(id: string) {
  if (getDataMode() === 'remote') {
    try {
      const result = await remoteGet<(typeof traces)[number]>(`/v1/traces/${encodeURIComponent(id)}`);
      if (!validateTraces([result])) throw new UpstreamError('INVALID_RESPONSE');
      return result;
    } catch (error) { if (error instanceof UpstreamError && error.code === 'NOT_FOUND') return null; throw error; }
  }
  return getLocalStore().traces().find((trace) => trace.id === id) ?? null;
}

export async function getOverviewMetrics() {
  if (getDataMode() === 'remote') return remoteGet<ReturnType<typeof calculateMetrics>>('/v1/metrics/overview');
  return calculateMetrics(getLocalStore().traces());
}

export async function getAlertRules() {
  const result = getDataMode() === 'remote' ? await remoteGet<typeof alertRules>('/v1/alerts') : getLocalStore().alerts().rules;
  if (!validAlertRules(result)) throw new UpstreamError('INVALID_RESPONSE');
  return result;
}

export async function getAlertState() { return getDataMode() === 'remote' ? { rules: await getAlertRules(), revision: 0 } : getLocalStore().alerts(); }
export function getLabels() { return getDataMode() === 'remote' ? [] : getLocalStore().labels(); }
