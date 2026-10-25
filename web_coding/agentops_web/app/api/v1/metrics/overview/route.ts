import { NextResponse } from 'next/server';
import { getTraces, getReferenceTime } from '@/lib/data-source';
import { apiResponse } from '@/lib/api-response';
import { filterTraces } from '@/lib/query';
import { calculateMetrics } from '@/lib/metrics';

export async function GET(request: Request) {
  return apiResponse(async () => {
    const params = new URL(request.url).searchParams;
    return { data: calculateMetrics(filterTraces(await getTraces(), params.get('project_id') || 'all', params.get('range') || 'all', getReferenceTime(), params.get('source') || 'all')) };
  });
}
