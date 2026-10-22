import { NextRequest, NextResponse } from 'next/server';
import { getTraces } from '@/lib/data-source';

export async function GET(request: NextRequest) {
  const traces = await getTraces();
  const projectId = request.nextUrl.searchParams.get('project_id');
  const status = request.nextUrl.searchParams.get('status');
  const query = request.nextUrl.searchParams.get('q')?.toLowerCase();
  const filtered = traces.filter((trace) =>
    (!projectId || projectId === 'all' || trace.projectId === projectId) &&
    (!status || status === 'all' || trace.status === status) &&
    (!query || trace.name.toLowerCase().includes(query) || trace.id.toLowerCase().includes(query)),
  );
  return NextResponse.json({ data: filtered, total: filtered.length });
}
