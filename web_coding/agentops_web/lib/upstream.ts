export class UpstreamError extends Error {
  constructor(public code: 'CONFIGURATION' | 'TIMEOUT' | 'UNAVAILABLE' | 'INVALID_RESPONSE' | 'NOT_FOUND') {
    super(code);
  }
}

export async function fetchUpstream<T>(base: string | undefined, path: string, token?: string): Promise<T> {
  if (!base) throw new UpstreamError('CONFIGURATION');
  let url: URL;
  try {
    url = new URL(base.replace(/\/$/, '') + path);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error();
  } catch { throw new UpstreamError('CONFIGURATION'); }
  try {
    const response = await fetch(url, {
      headers: { Accept: 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      signal: AbortSignal.timeout(8000), redirect: 'error', cache: 'no-store',
    });
    if (response.status === 404) throw new UpstreamError('NOT_FOUND');
    if (!response.ok) throw new UpstreamError('UNAVAILABLE');
    try { return await response.json() as T; } catch { throw new UpstreamError('INVALID_RESPONSE'); }
  } catch (error) {
    if (error instanceof UpstreamError) throw error;
    throw new UpstreamError(error instanceof Error && ['AbortError', 'TimeoutError'].includes(error.name) ? 'TIMEOUT' : 'UNAVAILABLE');
  }
}
