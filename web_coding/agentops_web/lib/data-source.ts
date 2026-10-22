import { alertRules, projects, traces } from './mock-data';
import { calculateMetrics } from './metrics';

export type DataMode = 'mock' | 'remote';

export function getDataMode(): DataMode {
  return process.env.AGENTOPS_DATA_MODE === 'remote' ? 'remote' : 'mock';
}

async function remoteGet<T>(path: string): Promise<T> {
  const baseUrl = process.env.AGENTOPS_API_URL;
  if (!baseUrl) throw new Error('AGENTOPS_API_URL is required in remote mode');
  const response = await fetch(`${baseUrl.replace(/\/$/, '')}${path}`, {
    headers: process.env.AGENTOPS_API_TOKEN
      ? { Authorization: `Bearer ${process.env.AGENTOPS_API_TOKEN}` }
      : undefined,
    cache: 'no-store',
  });
  if (!response.ok) throw new Error(`AgentOps API returned ${response.status}`);
  return response.json() as Promise<T>;
}

export async function getProjects() {
  return getDataMode() === 'remote' ? remoteGet<typeof projects>('/v1/projects') : projects;
}

export async function getTraces() {
  return getDataMode() === 'remote' ? remoteGet<typeof traces>('/v1/traces') : traces;
}

export async function getTrace(id: string) {
  if (getDataMode() === 'remote') return remoteGet<(typeof traces)[number]>(`/v1/traces/${id}`);
  return traces.find((trace) => trace.id === id) ?? null;
}

export async function getOverviewMetrics() {
  if (getDataMode() === 'remote') return remoteGet<ReturnType<typeof calculateMetrics>>('/v1/metrics/overview');
  return calculateMetrics(traces);
}

export async function getAlertRules() {
  return getDataMode() === 'remote' ? remoteGet<typeof alertRules>('/v1/alerts') : alertRules;
}
