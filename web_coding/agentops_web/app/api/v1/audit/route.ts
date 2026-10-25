import { apiResponse } from '@/lib/api-response';
import { getLocalStore } from '@/lib/local-store';
import { getDataMode } from '@/lib/data-source';
export const runtime = 'nodejs';
export async function GET() { return apiResponse(async () => ({ data: getDataMode() === 'remote' ? [] : getLocalStore().auditLog() })); }
