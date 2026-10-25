import { NextResponse } from 'next/server';
import { UpstreamError } from './upstream';
import { HttpError } from './http-error';

export async function apiResponse(action: () => Promise<unknown>) {
  const requestId = crypto.randomUUID();
  const headers = { 'Cache-Control': 'no-store', 'X-Request-Id': requestId };
  try { const result = await action(); return result instanceof Response ? result : NextResponse.json(result, { headers }); }
  catch (error) {
    if (error instanceof HttpError) return NextResponse.json({ error: { code: error.code, message: error.message, requestId } }, { status: error.status, headers });
    const code = error instanceof UpstreamError ? error.code : 'INTERNAL';
    const message = code === 'TIMEOUT' ? '数据源响应超时，请稍后重试。' : code === 'INVALID_RESPONSE' ? '数据源返回了不符合约定的数据。' : '数据源暂不可用，请检查服务端配置。';
    return NextResponse.json({ error: { code, message, requestId } }, { status: code === 'TIMEOUT' ? 504 : 502, headers });
  }
}
