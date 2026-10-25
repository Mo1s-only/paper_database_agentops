import { getDataMode, getProjects, getTraces } from '@/lib/data-source';
import { apiResponse } from '@/lib/api-response';
export const dynamic = 'force-dynamic';
export async function GET() {
  return apiResponse(async () => {
    const [projects, traces] = await Promise.all([getProjects(), getTraces()]);
    return { platform: 'agentops-web', status: 'ok', mode: getDataMode(), storage: getDataMode() === 'mock' ? 'sqlite' : 'remote', checkedAt: new Date().toISOString(), projects: projects.length, traces: traces.length, version: '0.3.0' };
  });
}
