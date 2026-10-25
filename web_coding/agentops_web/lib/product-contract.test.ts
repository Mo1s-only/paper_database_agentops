import { describe, expect, it, vi, afterEach } from 'vitest';
import { traces } from './mock-data';
import { filterTraces } from './query';
import { calculateMetrics } from './metrics';
import { validateTraces, validAlertRules } from './validation';
import { fetchUpstream } from './upstream';

afterEach(() => vi.unstubAllGlobals());
describe('product data contract', () => {
  it('filters the same project and time window used by the UI', () => {
    const anchor = Math.max(...traces.map((t) => Date.parse(t.startedAt)));
    expect(filterTraces(traces, 'all', '1h', anchor)).toHaveLength(2);
    expect(filterTraces(traces, 'research-copilot', '1h', anchor)).toHaveLength(1);
    expect(filterTraces(traces, 'missing', 'all', anchor)).toEqual([]);
    expect(filterTraces(traces, 'all', '24h', anchor + 2 * 86_400_000)).toEqual([]);
  });
  it('does not merge the same hour on different days', () => {
    const rows = [traces[0], { ...traces[0], startedAt: '2026-10-20T03:52:00Z' }];
    expect(calculateMetrics(rows).trend).toHaveLength(2);
  });
  it('rejects bad tree parents, cycles and nonnumeric metrics before rendering', () => {
    expect(validateTraces(traces)).toBe(true);
    const rows = structuredClone(traces);
    rows[0].spans[0].parentId = rows[0].spans[1].id;
    expect(validateTraces(rows)).toBe(false);
    rows[0].spans[0].parentId = 'missing';
    expect(validateTraces(rows)).toBe(false);
    rows[0].spans[0].parentId = null;
    rows[0].cost = Infinity;
    expect(validateTraces(rows)).toBe(false);
  });
  it('rejects malformed alert persistence', () => {
    expect(validAlertRules({ rules: [] })).toBe(false);
    expect(validAlertRules([{ id: '1', name: 'x', metric: 'error_rate', operator: '>', threshold: 101, channel: 'email', enabled: true }])).toBe(false);
  });
  it('preserves missing-resource errors and sanitizes network failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 404 })));
    await expect(fetchUpstream('https://example.com', '/v1/traces/absent')).rejects.toMatchObject({ code: 'NOT_FOUND' });
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('secret upstream URL')));
    await expect(fetchUpstream('https://example.com', '/v1/traces')).rejects.toMatchObject({ code: 'UNAVAILABLE', message: 'UNAVAILABLE' });
  });
});
