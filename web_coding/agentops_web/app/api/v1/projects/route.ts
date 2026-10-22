import { NextResponse } from 'next/server';
import { getProjects } from '@/lib/data-source';

export async function GET() {
  return NextResponse.json({ data: await getProjects() });
}
