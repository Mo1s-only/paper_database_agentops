import { getAlertState } from '@/lib/data-source';
import { getLocalStore } from '@/lib/local-store';
import { readWriteBody } from '@/lib/write-request';
import { apiResponse } from '@/lib/api-response';

export async function GET() {
  return apiResponse(async () => { const state = await getAlertState(); return { data: state.rules, revision: state.revision }; });
}
export async function PUT(request: Request) {
  return apiResponse(async () => {
    const body = await readWriteBody(request) as { rules?: unknown; revision?: unknown } | null;
    return { data: getLocalStore().saveAlerts(body?.rules, body?.revision) };
  });
}
