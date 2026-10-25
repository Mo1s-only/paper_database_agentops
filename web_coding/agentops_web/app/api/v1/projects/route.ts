import { getLocalStore } from '@/lib/local-store';
import { readWriteBody } from '@/lib/write-request';
import { getProjects } from '@/lib/data-source';
import { apiResponse } from '@/lib/api-response';

export async function GET() {
  return apiResponse(async () => ({ data: await getProjects() }));
}
export async function PUT(request: Request) { return apiResponse(async () => ({ data: getLocalStore().saveProject(await readWriteBody(request)) })); }
