import { HttpError } from './http-error';
import { validateTraces } from './validation';
import type { Trace } from './types';

export const MAX_IMPORT_BYTES = 5 * 1024 * 1024;
export const safeId = (value: unknown): value is string => typeof value === 'string' && /^[a-zA-Z0-9_-]{1,128}$/.test(value);
function fail(message: string): never { throw new HttpError(422, 'VALIDATION', message); }

/** Canonicalize only known fields. A user import is not a verified experiment. */
export function parseTraceImport(value: unknown, projectId: string): Trace[] {
  if (!safeId(projectId)) fail('请选择有效的目标项目。');
  const container = value as { traces?: unknown; data?: unknown } | null;
  const rows = Array.isArray(value) ? value : container?.traces ?? container?.data;
  if (!Array.isArray(rows) || rows.length === 0 || rows.length > 100) fail('每批需要 1–100 条 Trace。支持 Trace 数组、{ traces: [...] } 或 { data: [...] }。');
  let spanCount = 0;
  // Bound work before full graph validation, including adversarial deeply nested trees.
  for (const [index, row] of rows.entries()) {
    if (!row || !safeId(row.id) || typeof row.name !== 'string' || !row.name.trim() || row.name.length > 256 || !Array.isArray(row.spans)) fail(`第 ${index + 1} 条 Trace 的 ID、名称或 spans 不合法。ID 仅支持字母、数字、下划线和连字符。`);
    spanCount += row.spans.length;
    if (!row.spans.length || spanCount > 2000) fail('每条 Trace 至少需要一个 Span；单批最多 2000 个 Span。');
    for (const span of row.spans) {
      if (!span || !safeId(span.id) || (span.parentId !== null && !safeId(span.parentId)) || ['name', 'agent', 'input', 'output', 'model', 'error'].some((key) => span[key] !== undefined && (typeof span[key] !== 'string' || span[key].length > 65536))) fail(`Trace ${row.id} 含无效 Span 字段（文本最大 64 KiB 字符）。`);
    }
    if (!Array.isArray(row.tags) || row.tags.length > 50 || row.tags.some((tag: unknown) => typeof tag !== 'string' || tag.length > 128)) fail(`Trace ${row.id} 的标签不合法。`);
  }
  const mapped = rows.map((row): Trace => ({
    id: row.id, projectId, name: row.name.trim(), startedAt: row.startedAt, durationMs: row.durationMs,
    status: row.status, tokens: row.tokens, cost: row.cost, tags: [...new Set<string>(row.tags)],
    provenance: { kind: row.provenance?.kind === 'demo' ? 'demo' : 'imported' },
    spans: row.spans.map((s: Trace['spans'][number]) => ({ id: s.id, parentId: s.parentId, name: s.name, kind: s.kind, agent: s.agent, startedAt: s.startedAt, durationMs: s.durationMs, input: s.input, output: s.output, tokens: s.tokens, cost: s.cost, status: s.status, ...(s.model !== undefined && { model: s.model }), ...(s.error !== undefined && { error: s.error }) })),
  }));
  if (!validateTraces(mapped)) fail('Trace 校验失败：请检查时间、非负数值、必填字段、重复 ID，以及 Span 的父节点或循环引用。');
  for (const trace of mapped) {
    if (!Number.isSafeInteger(trace.tokens) || trace.spans.some((s) => !Number.isSafeInteger(s.tokens))) fail('Tokens 必须为非负安全整数。');
    const parents = new Map(trace.spans.map((s) => [s.id, s.parentId]));
    for (const span of trace.spans) {
      let cursor = span.parentId; let depth = 0;
      while (cursor !== null) { if (++depth > 128) fail('Span 嵌套深度不能超过 128 层。'); cursor = parents.get(cursor)!; }
    }
  }
  return mapped;
}
