import { NextRequest, NextResponse } from 'next/server';
import { getTraces, getReferenceTime } from '@/lib/data-source';
import { apiResponse } from '@/lib/api-response';
import { filterTraces } from '@/lib/query';

export async function GET(request: NextRequest) {
  return apiResponse(async () => {
  const traces = await getTraces();
  const projectId = request.nextUrl.searchParams.get('project_id');
  const status = request.nextUrl.searchParams.get('status');
  const query = request.nextUrl.searchParams.get('q')?.toLowerCase();
  const filtered = filterTraces(traces, projectId || 'all', request.nextUrl.searchParams.get('range') || 'all', getReferenceTime(), request.nextUrl.searchParams.get('source') || 'all').filter((trace) =>
    (!projectId || projectId === 'all' || trace.projectId === projectId) &&
    (!status || status === 'all' || trace.status === status) &&
    (!query || trace.name.toLowerCase().includes(query) || trace.id.toLowerCase().includes(query)),
  );
  return { data: filtered, total: filtered.length };
  });
}
