'use client';
import { useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { FileJson, Upload, CheckCircle2 } from 'lucide-react';
import { parseTraceImport, MAX_IMPORT_BYTES } from '@/lib/import-contract';
import { writeApi } from '@/lib/api-client';
import type { Trace } from '@/lib/types';
import { Modal } from './modal';
import { useDashboard } from './dashboard-context';
import { useToast } from './toast';

export function TraceImport({ onImported }: { onImported: () => void }) {
  const { projects, selectedProjectId, setSelectedProjectId, setTimeRange, dataMode } = useDashboard();
  const [open, setOpen] = useState(false);
  const [project, setProject] = useState('');
  const [content, setContent] = useState('');
  const [preview, setPreview] = useState<Trace[] | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const readVersion = useRef(0);
  const router = useRouter(); const toast = useToast();
  if (dataMode === 'remote') return null;
  function inspect() {
    setError(''); setPreview(null);
    try {
      if (new TextEncoder().encode(content).length > MAX_IMPORT_BYTES) throw new Error('文件最大为 5 MiB。');
      const rows = parseTraceImport(JSON.parse(content), project); setPreview(rows);
    } catch (error) { setError(error instanceof SyntaxError ? 'JSON 格式不合法，请检查后重新校验。' : error instanceof Error ? error.message : '校验失败'); }
  }
  async function upload(file?: File) {
    const version = ++readVersion.current; setPreview(null); setError(''); setContent('');
    if (!file) return;
    if (file.size > MAX_IMPORT_BYTES) { setError('文件最大为 5 MiB。'); return; }
    try { const text = await file.text(); if (version === readVersion.current) setContent(text); }
    catch { if (version === readVersion.current) setError('文件读取失败，请重试。'); }
  }
  async function commit() {
    if (!preview) return;
    setBusy(true); setError('');
    try {
      const result = await writeApi<{ count: number }>('/api/v1/traces/import', { projectId: project, traces: preview });
      setSelectedProjectId(project); setTimeRange('all'); onImported(); router.refresh(); setOpen(false);
      toast(`${result.count} 条 Trace 已保存。已切换到目标项目和全部时间。`);
    } catch (error) { setError(error instanceof Error ? error.message : '导入失败。网络超时后可先刷新确认，重复 ID 不会重复入库。'); }
    finally { setBusy(false); }
  }
  return <><button className="button primary" onClick={() => { setProject(selectedProjectId !== 'all' ? selectedProjectId : projects[0]?.id ?? ''); setContent(''); setPreview(null); setError(''); setOpen(true); }}><Upload size={16} />导入 Trace</button>
    {open && <Modal title="导入 Trace 数据" onClose={() => { if (!busy) { readVersion.current++; setOpen(false); } }}>
      <p className="form-note">标准化 JSON → 结构校验 → 本机持久化。所有记录将归属所选项目；同 ID 整批拒绝，不覆盖已有数据。不是 AgentOps SDK / OTLP 接收端。</p>
      <label className="field"><span>目标项目</span><select disabled={busy} value={project} onChange={(e) => { setProject(e.target.value); setPreview(null); }}>{projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      <label className="import-file"><FileJson size={22} /><span>选择 JSON 文件<small>最大 5 MiB · 100 Traces · 2000 Spans</small></span><input aria-label="选择 Trace JSON 文件" type="file" accept=".json,application/json" disabled={busy} onChange={(e) => upload(e.target.files?.[0])} /></label>
      <label className="field"><span>或粘贴 Trace JSON</span><textarea className="import-json" spellCheck={false} disabled={busy} value={content} onChange={(e) => { readVersion.current++; setContent(e.target.value); setPreview(null); setError(''); }} placeholder={'[{ "id": "trace_001", "spans": [...] }]'} /></label>
      <a className="text-link" href="/examples/trace-import.json" download>下载结构示例（明确标记为演示数据）</a>
      {preview && <div className="import-preview"><CheckCircle2 size={18} /><div><strong>结构校验通过</strong><p>{preview.length} 条 Trace · {preview.reduce((sum, t) => sum + t.spans.length, 0)} 个 Span · {preview.filter((t) => t.provenance?.kind === 'demo').length} 条明确标记为示例</p><small>输入 / 输出可能含敏感信息，请确认已脱敏。导入不代表来源真实性已核验。</small></div></div>}
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="modal-actions"><button className="button secondary" disabled={busy || !content.trim()} onClick={inspect}>校验并预览</button><button className="button primary" disabled={!preview || busy} onClick={commit}>{busy ? '导入中…' : '确认导入'}</button></div>
    </Modal>}
  </>;
}
