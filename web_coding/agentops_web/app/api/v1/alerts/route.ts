import { NextResponse } from 'next/server';
import { getAlertRules } from '@/lib/data-source';

export async function GET() {
  return NextResponse.json({ data: await getAlertRules() });
}
