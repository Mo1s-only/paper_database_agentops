import type { DatabaseSync as Database } from 'node:sqlite';
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { randomUUID } from 'node:crypto';
import { projects as demoProjects, traces as demoTraces, alertRules } from './mock-data';
import { HttpError } from './http-error';
import { parseTraceImport, safeId } from './import-contract';
import { validAlertRules } from './validation';
import type { AlertRule, GroundTruthLabel, Project, Trace } from './types';

type Row = { payload: string; revision: number };
// Keep the Node 24 built-in outside older Vite dependency transforms.
const { DatabaseSync } = process.getBuiltinModule('node:sqlite') as typeof import('node:sqlite');
export class LocalStore {
  private db: Database;
  constructor(path: string) {
    if (path !== ':memory:') mkdirSync(dirname(path), { recursive: true });
    this.db = new DatabaseSync(path);
    this.db.exec(`PRAGMA busy_timeout=5000; PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
      CREATE TABLE IF NOT EXISTS documents (kind TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, revision INTEGER NOT NULL, PRIMARY KEY(kind,id));
      CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, entity TEXT NOT NULL, metadata TEXT NOT NULL, created_at TEXT NOT NULL);
      PRAGMA user_version=1;`);
    this.transaction(() => {
      const seed = this.db.prepare('INSERT OR IGNORE INTO documents VALUES (?,?,?,1)');
      for (const project of demoProjects) seed.run('project', project.id, JSON.stringify(project));
      seed.run('alerts', 'workspace', JSON.stringify(alertRules));
    });
  }
  close() { this.db.close(); }
  private transaction<T>(action: () => T): T {
    this.db.exec('BEGIN IMMEDIATE');
    try { const result = action(); this.db.exec('COMMIT'); return result; }
    catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }
  private row(kind: string, id: string) { return this.db.prepare('SELECT payload,revision FROM documents WHERE kind=? AND id=?').get(kind, id) as Row | undefined; }
  private list<T>(kind: string): T[] { return (this.db.prepare('SELECT payload,revision FROM documents WHERE kind=? ORDER BY id').all(kind) as Row[]).map((r) => ({ ...JSON.parse(r.payload), revision: r.revision })); }
  private put(kind: string, id: string, payload: unknown, expected: unknown) {
    const revision = this.row(kind, id)?.revision ?? 0;
    if (!Number.isSafeInteger(expected) || expected !== revision) throw new HttpError(409, 'CONFLICT', '数据已变更或版本不匹配，请刷新后重试；当前草稿尚未写入。');
    this.db.prepare('INSERT INTO documents VALUES (?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET payload=excluded.payload,revision=excluded.revision').run(kind, id, JSON.stringify(payload), revision + 1);
    return revision + 1;
  }
  private audit(action: string, entity: string, metadata: unknown) { this.db.prepare('INSERT INTO audit(action,entity,metadata,created_at) VALUES (?,?,?,?)').run(action, entity, JSON.stringify(metadata), new Date().toISOString()); }
  projects() { return this.list<Project>('project'); }
  traces(): Trace[] { return [...demoTraces.map((t): Trace => ({ ...t, provenance: { kind: 'demo' } })), ...this.list<Trace>('trace')]; }
  labels() { return this.list<GroundTruthLabel>('label'); }
  alerts() { const row = this.row('alerts', 'workspace')!; return { rules: JSON.parse(row.payload) as AlertRule[], revision: row.revision }; }
  auditLog() { return this.db.prepare('SELECT id,action,entity,metadata,created_at AS createdAt FROM audit ORDER BY id DESC LIMIT 100').all(); }
  saveProject(value: unknown) {
    const p = value as Project | null;
    if (!p || !safeId(p.id) || typeof p.name !== 'string' || !p.name.trim() || p.name.trim().length > 80 || !['production', 'staging', 'development'].includes(p.environment)) throw new HttpError(422, 'VALIDATION', '项目名称、ID 或环境不合法。');
    return this.transaction(() => {
      const existing = this.projects();
      if (existing.some((r) => r.id !== p.id && r.name.toLocaleLowerCase() === p.name.trim().toLocaleLowerCase())) throw new HttpError(409, 'DUPLICATE_NAME', '该项目名称已存在。');
      const previous = existing.find((r) => r.id === p.id);
      const project: Project = { id: p.id, name: p.name.trim(), environment: p.environment, apiKeyHint: previous?.apiKeyHint ?? '尚未配置', traces24h: 0 };
      const revision = this.put('project', p.id, project, p.revision ?? 0);
      this.audit('project.saved', p.id, { revision });
      return { ...project, revision };
    });
  }
  saveAlerts(value: unknown, expected: unknown) {
    if (!validAlertRules(value) || value.length > 100 || value.some((r) => !safeId(r.id) || r.name.length > 80) || new Set(value.map((r) => r.id)).size !== value.length || new Set(value.map((r) => r.name.trim().toLowerCase())).size !== value.length) throw new HttpError(422, 'VALIDATION', '策略名称、ID、阈值不合法或重复；最多 100 条策略。');
    const rules = value.map((r): AlertRule => ({ id: r.id, name: r.name.trim(), metric: r.metric, operator: '>', threshold: r.threshold, channel: r.channel, enabled: r.enabled }));
    return this.transaction(() => { const revision = this.put('alerts', 'workspace', rules, expected); this.audit('alerts.saved', 'workspace', { count: rules.length, revision }); return { rules, revision }; });
  }
  importTraces(value: unknown, projectId: string) {
    const traces = parseTraceImport(value, projectId);
    return this.transaction(() => {
      if (!this.row('project', projectId)) throw new HttpError(422, 'PROJECT_NOT_FOUND', '目标项目不存在。');
      const existing = new Set(this.traces().map((t) => t.id));
      const duplicate = traces.find((t) => existing.has(t.id));
      if (duplicate) throw new HttpError(409, 'DUPLICATE_TRACE', `Trace ${duplicate.id} 已存在，整批未导入。请使用新的唯一 ID。`);
      const batchId = randomUUID(); const importedAt = new Date().toISOString();
      for (const trace of traces) this.put('trace', trace.id, { ...trace, provenance: { ...trace.provenance, batchId, importedAt } }, 0);
      this.audit('traces.imported', batchId, { projectId, count: traces.length });
      return { count: traces.length, batchId, ids: traces.map((t) => t.id) };
    });
  }
  saveLabel(value: unknown) {
    const label = value as GroundTruthLabel | null;
    if (!label || !safeId(label.traceId) || !safeId(label.rootSpanId) || !['tool_failure', 'llm_failure', 'handoff_failure', 'workflow_failure', 'other'].includes(label.failureType) || typeof label.note !== 'string' || !label.note.trim() || label.note.length > 4000) throw new HttpError(422, 'VALIDATION', '请选择根因并填写证据说明（1–4000 字符）。');
    return this.transaction(() => {
      const trace = this.traces().find((t) => t.id === label.traceId);
      if (!trace || trace.status !== 'error' || !trace.spans.some((s) => s.id === label.rootSpanId)) throw new HttpError(422, 'INVALID_LABEL', '标签必须对应失败 Trace 中存在的 Span。');
      const saved: GroundTruthLabel = { traceId: label.traceId, rootSpanId: label.rootSpanId, failureType: label.failureType, note: label.note.trim(), createdAt: new Date().toISOString() };
      const revision = this.put('label', label.traceId, saved, label.revision ?? 0);
      this.audit('label.saved', label.traceId, { rootSpanId: label.rootSpanId, revision });
      return { ...saved, revision };
    });
  }
}

const globalStore = globalThis as typeof globalThis & { agentopsLocalStoreV1?: LocalStore };
export function getLocalStore() {
  return globalStore.agentopsLocalStoreV1 ??= new LocalStore(resolve(/* turbopackIgnore: true */ process.env.AGENTOPS_DB_PATH ?? '.data/agentops.sqlite'));
}
