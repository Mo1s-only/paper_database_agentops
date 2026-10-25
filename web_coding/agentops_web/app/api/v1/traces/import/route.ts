import { apiResponse } from '@/lib/api-response';
import { readWriteBody } from '@/lib/write-request';
import { getLocalStore } from '@/lib/local-store';

export const runtime = 'nodejs';
export async function POST(request: Request) {
  return apiResponse(async () => {
    const body = await readWriteBody(request) as { traces?: unknown; projectId?: string } | null;
    return { data: getLocalStore().importTraces(body?.traces, body?.projectId ?? '') };
  });
}
