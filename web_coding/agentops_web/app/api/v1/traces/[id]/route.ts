import { NextResponse } from 'next/server';
import { getTrace } from '@/lib/data-source';
import { apiResponse } from '@/lib/api-response';

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return apiResponse(async () => {
    const trace = await getTrace(id);
    if (!trace) return NextResponse.json({ error: 'Trace not found' }, { status: 404 });
    return { data: trace };
  });
}
