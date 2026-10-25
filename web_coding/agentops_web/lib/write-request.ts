import { HttpError } from './http-error';
import { MAX_IMPORT_BYTES } from './import-contract';

export function assertLocalWrite(request: Request) {
  const target = new URL(request.url);
  const origin = request.headers.get('origin');
  const host = request.headers.get('host');
  if (process.env.AGENTOPS_DATA_MODE === 'remote') throw new HttpError(403, 'READ_ONLY', '远程模式暂不支持写入。');
  if (!['localhost', '127.0.0.1', '[::1]'].includes(target.hostname) || host !== target.host || origin !== target.origin || request.headers.get('x-agentops-client') !== 'web' || request.headers.get('sec-fetch-site') === 'cross-site') {
    throw new HttpError(403, 'LOCAL_ONLY', '写入仅允许本机同源工作区；此限制不替代生产环境身份认证。');
  }
  if (request.headers.get('content-type')?.split(';')[0].trim() !== 'application/json') throw new HttpError(415, 'CONTENT_TYPE', '请求必须使用 application/json。');
}

export async function readWriteBody(request: Request): Promise<unknown> {
  assertLocalWrite(request);
  if (Number(request.headers.get('content-length')) > MAX_IMPORT_BYTES) throw new HttpError(413, 'TOO_LARGE', '请求不能超过 5 MiB。');
  if (!request.body) throw new HttpError(400, 'INVALID_JSON', '请求内容为空。');
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = []; let size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read(); if (done) break;
      size += value.byteLength;
      if (size > MAX_IMPORT_BYTES) { await reader.cancel(); throw new HttpError(413, 'TOO_LARGE', '请求不能超过 5 MiB。'); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  const data = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { data.set(chunk, offset); offset += chunk.byteLength; }
  try { return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(data)); }
  catch { throw new HttpError(400, 'INVALID_JSON', 'JSON 无法解析，请检查文件格式。'); }
}
