import { NextResponse } from 'next/server';
import { getOverviewMetrics } from '@/lib/data-source';

export async function GET() {
  return NextResponse.json({ data: await getOverviewMetrics() });
}
