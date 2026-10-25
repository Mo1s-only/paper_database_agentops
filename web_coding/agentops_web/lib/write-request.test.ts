import { afterEach, describe, expect, it, vi } from 'vitest';
import { assertLocalWrite, readWriteBody } from './write-request';
import { MAX_IMPORT_BYTES } from './import-contract';
import { apiResponse } from './api-response';
import { HttpError } from './http-error';

function request(options: { origin?: string; host?: string; contentType?: string; client?: string; body?: string } = {}) {
  return new Request('http://127.0.0.1:3017/api/v1/projects', { method: 'PUT', headers: { Origin: options.origin ?? 'http://127.0.0.1:3017', Host: options.host ?? '127.0.0.1:3017', 'Content-Type': options.contentType ?? 'application/json', 'X-AgentOps-Client': options.client ?? 'web' }, body: options.body ?? '{}' });
}
afterEach(() => vi.unstubAllEnvs());
describe('local write boundary', () => {
  it('accepts local same-origin JSON requests', async () => {
    vi.stubEnv('AGENTOPS_DATA_MODE', 'mock');
    expect(() => assertLocalWrite(request())).not.toThrow();
    expect(await readWriteBody(request({ body: '{"name":"测试"}' }))).toEqual({ name: '测试' });
  });
  it('rejects cross-origin, missing custom header, mismatched host and remote mode', () => {
    expect(() => assertLocalWrite(request({ origin: 'https://external.example' }))).toThrow(/同源/);
    expect(() => assertLocalWrite(request({ client: '' }))).toThrow(/同源/);
    expect(() => assertLocalWrite(request({ host: 'evil.example' }))).toThrow(/同源/);
    vi.stubEnv('AGENTOPS_DATA_MODE', 'remote');
    expect(() => assertLocalWrite(request())).toThrow(/远程模式/);
  });
  it('rejects non-JSON, malformed JSON and oversized bodies without trusting Content-Length', async () => {
    expect(() => assertLocalWrite(request({ contentType: 'text/plain' }))).toThrow(/application\/json/);
    await expect(readWriteBody(request({ body: '{invalid' }))).rejects.toMatchObject({ status: 400 });
    await expect(readWriteBody(request({ body: ' '.repeat(MAX_IMPORT_BYTES + 1) }))).rejects.toMatchObject({ status: 413 });
  });
  it('returns actionable error status, no-store and a correlation ID', async () => {
    const response = await apiResponse(async () => { throw new HttpError(409, 'CONFLICT', 'Refresh before saving'); });
    expect(response.status).toBe(409);
    expect(response.headers.get('cache-control')).toBe('no-store');
    const body = await response.json();
    expect(body.error.requestId).toBe(response.headers.get('x-request-id'));
    expect(body.error.code).toBe('CONFLICT');
  });
});
