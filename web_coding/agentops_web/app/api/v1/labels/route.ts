import { apiResponse } from '@/lib/api-response';
import { readWriteBody } from '@/lib/write-request';
import { getLocalStore } from '@/lib/local-store';
import { getLabels } from '@/lib/data-source';
export const runtime = 'nodejs';
export async function GET() { return apiResponse(async () => ({ data: getLabels() })); }
export async function PUT(request: Request) { return apiResponse(async () => ({ data: getLocalStore().saveLabel(await readWriteBody(request)) })); }
