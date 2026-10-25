import { afterEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { LocalStore } from './local-store';
import { traces, projects } from './mock-data';
import { parseTraceImport } from './import-contract';
import { filterTraces } from './query';

const stores: LocalStore[] = [];
const directories: string[] = [];
const memory = () => { const store = new LocalStore(':memory:'); stores.push(store); return store; };
const sample = (id = 'imported_1') => ({ ...structuredClone(traces[0]), id });
afterEach(() => { for (const store of stores.splice(0)) store.close(); for (const directory of directories.splice(0)) rmSync(directory, { recursive: true, force: true }); });

describe('durable local workspace', () => {
  it('persists projects, alerts, imports and labels after reopen without reseeding over edits', () => {
    const dir = mkdtempSync(join(tmpdir(), 'agentops-store-test-')); directories.push(dir);
    const path = join(dir, 'test.sqlite');
    const first = new LocalStore(path);
    const project = first.saveProject({ id: 'test_project', name: 'Durable project', environment: 'development' });
    const failure = { ...sample(), status: 'error' as const };
    first.importTraces([failure], project.id);
    first.saveAlerts([], first.alerts().revision);
    first.saveLabel({ traceId: failure.id, rootSpanId: failure.spans[0].id, failureType: 'other', note: 'Test evidence, not an experiment result.' });
    first.close();
    const reopened = new LocalStore(path); stores.push(reopened);
    expect(reopened.projects().find((p) => p.id === project.id)?.revision).toBe(1);
    expect(reopened.alerts().rules).toEqual([]);
    expect(reopened.labels()[0].note).toContain('Test evidence');
    expect(reopened.traces().find((t) => t.id === failure.id)?.provenance).toMatchObject({ kind: 'imported' });
    expect(reopened.auditLog()).toHaveLength(4);
  });
  it('rejects stale project and alert writes instead of silently overwriting', () => {
    const store = memory(); const original = store.projects()[0];
    store.saveProject({ ...original, name: 'Updated once' });
    expect(() => store.saveProject({ ...original, name: 'Stale update' })).toThrow(/版本/);
    const alerts = store.alerts(); store.saveAlerts([], alerts.revision);
    expect(() => store.saveAlerts(alerts.rules, alerts.revision)).toThrow(/版本/);
    expect(store.projects().find((p) => p.id === original.id)?.name).toBe('Updated once');
    expect(store.auditLog()).toHaveLength(2);
  });
  it('validates project names and alert uniqueness on the server', () => {
    const store = memory();
    expect(() => store.saveProject({ id: 'new_id', name: projects[0].name.toUpperCase(), environment: 'production' })).toThrow(/名称/);
    expect(() => store.saveProject({ id: '../unsafe', name: 'x', environment: 'production' })).toThrow(/不合法/);
    const rules = store.alerts().rules;
    expect(() => store.saveAlerts([rules[0], rules[0]], 1)).toThrow(/重复/);
  });
  it('imports transactionally and refuses existing IDs, including built-in fixtures', () => {
    const store = memory();
    expect(() => store.importTraces([sample(), traces[0]], projects[0].id)).toThrow(/整批未导入/);
    expect(store.traces()).toHaveLength(traces.length);
    expect(store.auditLog()).toEqual([]);
    store.importTraces([sample()], projects[0].id);
    expect(() => store.importTraces([sample()], projects[0].id)).toThrow(/已存在/);
    expect(store.auditLog()).toHaveLength(1);
  });
  it('rejects nonexistent projects and labels that do not belong to a failing trace', () => {
    const store = memory();
    expect(() => store.importTraces([sample()], 'missing_project')).toThrow(/项目不存在/);
    const failure = traces.find((t) => t.status === 'error')!;
    expect(() => store.saveLabel({ traceId: failure.id, rootSpanId: 'missing', failureType: 'other', note: 'Evidence' })).toThrow(/存在的 Span/);
    expect(() => store.saveLabel({ traceId: failure.id, rootSpanId: failure.spans[0].id, failureType: 'other', note: '' })).toThrow(/证据/);
    const label = store.saveLabel({ traceId: failure.id, rootSpanId: failure.spans[0].id, failureType: 'other', note: 'Evidence' });
    expect(label.revision).toBe(1);
    expect(() => store.saveLabel({ ...label, revision: 0 })).toThrow(/版本/);
  });
  it('keeps demo provenance and strips untrusted revision and extra fields', () => {
    const row = { ...sample(), revision: 999, secret: 'not persisted', provenance: { kind: 'demo', batchId: 'spoofed' } };
    const parsed = parseTraceImport({ data: [row] }, projects[0].id);
    expect(parsed[0].projectId).toBe(projects[0].id);
    expect(parsed[0]).not.toHaveProperty('secret');
    expect(parsed[0]).not.toHaveProperty('revision');
    expect(parsed[0].provenance).toEqual({ kind: 'demo' });
    expect(filterTraces(parsed, 'all', 'all', Date.now(), 'imported')).toEqual([]);
  });
  it('bounds payload complexity and rejects invalid graph/optional fields', () => {
    expect(() => parseTraceImport([], projects[0].id)).toThrow(/1–100/);
    expect(() => parseTraceImport(Array.from({ length: 101 }, () => sample()), projects[0].id)).toThrow(/1–100/);
    const row = sample(); row.spans[0].parentId = row.spans[0].id;
    expect(() => parseTraceImport([row], projects[0].id)).toThrow(/循环/);
    expect(() => parseTraceImport([{ ...sample(), tokens: 1.1 }], projects[0].id)).toThrow(/整数/);
    const invalid = sample(); (invalid.spans[0] as unknown as Record<string, unknown>).model = { nested: 'bad' };
    expect(() => parseTraceImport([invalid], projects[0].id)).toThrow(/Span/);
  });
  it('observes concurrent revisions across two database connections', () => {
    const dir = mkdtempSync(join(tmpdir(), 'agentops-concurrency-test-')); directories.push(dir);
    const path = join(dir, 'test.sqlite');
    const first = new LocalStore(path); const second = new LocalStore(path); stores.push(first, second);
    const stale = second.projects()[0]; first.saveProject({ ...stale, name: 'Concurrent writer' });
    expect(() => second.saveProject({ ...stale, name: 'Lost update' })).toThrow(/版本/);
  });
});
