export async function writeApi<T>(path: string, value: unknown, method = 'POST'): Promise<T> {
  const response = await fetch(path, { method, headers: { 'Content-Type': 'application/json', 'X-AgentOps-Client': 'web' }, body: JSON.stringify(value), signal: AbortSignal.timeout(15000) });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error?.message ?? '保存失败，请稍后重试。');
  return body.data as T;
}
