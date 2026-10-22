'use client';

import { AlertTriangle, ArrowLeft, Braces, Check, ChevronDown, ChevronRight, Clock3, Coins, Copy, Cpu, Download, FileCheck2, FlaskConical, GitBranch, MessageSquareText, Network, PenLine, Play, ScanSearch, TerminalSquare, X } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { StatusBadge } from './ui';
import type { GroundTruthLabel, Span, Trace } from '@/lib/types';
import { formatCompact, formatCost, formatDateTime, formatDuration } from '@/lib/format';
import { attributeFailure } from '@/lib/attribution';

const kindIcon = { workflow: Network, agent: Cpu, llm: MessageSquareText, tool: TerminalSquare };

export function TraceDetail({ trace }: { trace: Trace }) {
  const [selectedSpanId, setSelectedSpanId] = useState(trace.spans[0]?.id ?? '');
  const [expanded, setExpanded] = useState<string[]>(trace.spans.map((span) => span.id));
  const [tab, setTab] = useState<'overview' | 'input' | 'output' | 'raw'>('overview');
  const [view, setView] = useState<'replay' | 'attribution'>('replay');
  const [copied, setCopied] = useState(false);
  const [groundTruth, setGroundTruth] = useState<GroundTruthLabel | null>(null);
  const [annotationOpen, setAnnotationOpen] = useState(false);
  const [labelSpanId, setLabelSpanId] = useState('');
  const [failureType, setFailureType] = useState<GroundTruthLabel['failureType']>('tool_failure');
  const [labelNote, setLabelNote] = useState('');
  const selected = trace.spans.find((span) => span.id === selectedSpanId) ?? trace.spans[0];
  const rootStart = new Date(trace.startedAt).getTime();
  const attribution = useMemo(() => attributeFailure(trace), [trace]);
  const attributedSpan = trace.spans.find((span) => span.id === attribution.rootSpanId);
  const pathSpans = attribution.propagationPath.map((id) => trace.spans.find((span) => span.id === id)).filter((span): span is Span => Boolean(span));

  useEffect(() => {
    try {
      const labels = JSON.parse(window.localStorage.getItem('agentops-ground-truth') ?? '[]') as GroundTruthLabel[];
      const current = labels.find((label) => label.traceId === trace.id) ?? null;
      setGroundTruth(current);
      setLabelSpanId(current?.rootSpanId ?? attribution.rootSpanId ?? trace.spans[0]?.id ?? '');
      setFailureType(current?.failureType ?? 'tool_failure');
      setLabelNote(current?.note ?? '');
    } catch {
      setGroundTruth(null);
    }
  }, [attribution.rootSpanId, trace.id, trace.spans]);

  const children = useMemo(() => {
    const map = new Map<string | null, Span[]>();
    trace.spans.forEach((span) => map.set(span.parentId, [...(map.get(span.parentId) ?? []), span]));
    return map;
  }, [trace.spans]);

  const toggle = (id: string) => setExpanded((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  const copyId = async () => { await navigator.clipboard.writeText(trace.id); setCopied(true); window.setTimeout(() => setCopied(false), 1200); };
  const saveGroundTruth = () => {
    const label: GroundTruthLabel = { traceId: trace.id, rootSpanId: labelSpanId, failureType, note: labelNote.trim(), createdAt: new Date().toISOString() };
    let labels: GroundTruthLabel[] = [];
    try { labels = JSON.parse(window.localStorage.getItem('agentops-ground-truth') ?? '[]') as GroundTruthLabel[]; } catch { labels = []; }
    const next = [...labels.filter((item) => item.traceId !== trace.id), label];
    window.localStorage.setItem('agentops-ground-truth', JSON.stringify(next));
    setGroundTruth(label);
    setAnnotationOpen(false);
  };
  const exportGroundTruth = () => {
    if (!groundTruth) return;
    const blob = new Blob([JSON.stringify({ schemaVersion: '0.1.0', label: groundTruth }, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${trace.id}-ground-truth.json`; anchor.click(); URL.revokeObjectURL(url);
  };

  const renderSpans = (parentId: string | null, depth = 0): React.ReactNode => (children.get(parentId) ?? []).map((span) => {
    const nested = children.get(span.id) ?? [];
    const isExpanded = expanded.includes(span.id);
    const Icon = kindIcon[span.kind];
    const offset = Math.max(0, new Date(span.startedAt).getTime() - rootStart);
    const left = (offset / Math.max(trace.durationMs, 1)) * 100;
    const width = Math.max(2, (span.durationMs / Math.max(trace.durationMs, 1)) * 100);
    return (
      <div key={span.id}>
        <button className={`span-row ${selectedSpanId === span.id ? 'selected' : ''}`} onClick={() => setSelectedSpanId(span.id)}>
          <span className="span-name" style={{ paddingLeft: `${depth * 18}px` }}>
            {nested.length ? <i className="expand-toggle" onClick={(event) => { event.stopPropagation(); toggle(span.id); }}>{isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</i> : <i className="expand-spacer" />}
            <i className={`span-kind kind-${span.kind}`}><Icon size={14} /></i>
            <span><strong>{span.name}</strong><small>{span.agent}</small></span>
          </span>
          <span className="waterfall"><i className={`waterfall-bar status-${span.status}`} style={{ left: `${left}%`, width: `${Math.min(100 - left, width)}%` }}><em>{formatDuration(span.durationMs)}</em></i></span>
        </button>
        {isExpanded && renderSpans(span.id, depth + 1)}
      </div>
    );
  });

  return (
    <div className="trace-detail-page">
      <div className="trace-breadcrumb"><Link href="/traces"><ArrowLeft size={16} />返回 Trace 列表</Link><span>/</span><code>{trace.id}</code></div>
      <div className="trace-detail-head">
        <div><span className="eyebrow">Trace replay</span><h1>{trace.name}</h1><button className="copy-id" onClick={copyId}><code>{trace.id}</code>{copied ? <Check size={14} /> : <Copy size={14} />}</button></div>
        <StatusBadge status={trace.status} />
      </div>
      <section className="trace-summary-strip">
        <div><Clock3 size={16} /><span>开始时间</span><strong>{formatDateTime(trace.startedAt)}</strong></div>
        <div><Play size={16} /><span>总耗时</span><strong>{formatDuration(trace.durationMs)}</strong></div>
        <div><Network size={16} /><span>Spans</span><strong>{trace.spans.length}</strong></div>
        <div><Braces size={16} /><span>Tokens</span><strong>{formatCompact(trace.tokens)}</strong></div>
        <div><Coins size={16} /><span>成本</span><strong>{formatCost(trace.cost)}</strong></div>
        <div><AlertTriangle size={16} /><span>错误</span><strong>{trace.spans.filter((span) => span.status === 'error').length}</strong></div>
      </section>

      <div className="detail-view-tabs" role="tablist" aria-label="Trace 详情视图">
        <button className={view === 'replay' ? 'active' : ''} onClick={() => setView('replay')}><Play size={15} />执行回放</button>
        <button className={view === 'attribution' ? 'active' : ''} onClick={() => setView('attribution')}><ScanSearch size={15} />失败归因{trace.status === 'error' && <i />}</button>
      </div>

      {view === 'replay' ? <section className="trace-workspace">
        <article className="panel waterfall-panel">
          <div className="panel-head"><div><span className="eyebrow">Execution tree</span><h2>Span 时间线</h2></div><div className="waterfall-scale"><span>0s</span><span>25%</span><span>50%</span><span>75%</span><span>{formatDuration(trace.durationMs)}</span></div></div>
          <div className="span-list">{renderSpans(null)}</div>
        </article>

        <aside className="panel inspector-panel">
          {selected ? <>
            <div className="inspector-head"><i className={`span-kind kind-${selected.kind}`}>{(() => { const Icon = kindIcon[selected.kind]; return <Icon size={17} />; })()}</i><div><span>{selected.kind}</span><h2>{selected.name}</h2></div></div>
            <div className="tabs" role="tablist">
              {(['overview', 'input', 'output', 'raw'] as const).map((item) => <button key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>{({ overview: '概览', input: '输入', output: '输出', raw: '原始数据' })[item]}</button>)}
            </div>
            <div className="inspector-content">
              {tab === 'overview' && <div className="property-list"><div><span>Agent</span><strong>{selected.agent}</strong></div><div><span>状态</span><StatusBadge status={selected.status} /></div><div><span>耗时</span><strong>{formatDuration(selected.durationMs)}</strong></div><div><span>模型</span><strong>{selected.model ?? '—'}</strong></div><div><span>Tokens</span><strong>{formatCompact(selected.tokens)}</strong></div><div><span>成本</span><strong>{formatCost(selected.cost)}</strong></div>{selected.error && <div className="error-box"><AlertTriangle size={16} /><span>{selected.error}</span></div>}</div>}
              {tab === 'input' && <pre>{selected.input}</pre>}
              {tab === 'output' && <pre>{selected.output}</pre>}
              {tab === 'raw' && <pre>{JSON.stringify(selected, null, 2)}</pre>}
            </div>
          </> : <p>请选择一个 Span</p>}
        </aside>
      </section> : <section className="attribution-workspace">
        <div className="research-boundary"><FlaskConical size={18} /><p><strong>UNVERIFIED · 演示启发式</strong><span>结果来自透明规则基线，用于验证界面与数据契约，不代表论文实验结论。</span></p><code>{attribution.method}@{attribution.methodVersion}</code></div>
        {trace.status === 'error' && (groundTruth ? <div className="ground-truth verified"><FileCheck2 size={18} /><p><strong>VERIFIED HUMAN LABEL</strong><span>人工标注根因：{trace.spans.find((span) => span.id === groundTruth.rootSpanId)?.name ?? groundTruth.rootSpanId} · {groundTruth.failureType}</span></p><button onClick={exportGroundTruth}><Download size={14} />导出</button><button onClick={() => setAnnotationOpen(true)}><PenLine size={14} />编辑</button></div> : <div className="ground-truth needed"><PenLine size={18} /><p><strong>AUTHOR_INPUT_NEEDED</strong><span>尚无人工 Ground Truth；自动候选不能用于计算归因准确率。</span></p><button onClick={() => setAnnotationOpen(true)}>标注根因</button></div>)}
        {attribution.status === 'no_failure' ? <article className="panel no-attribution"><span><Check size={22} /></span><h2>该 Trace 没有失败 Span</h2><p>当前规则不会为成功执行强行生成根因。若要研究隐性质量失败，需要额外接入任务结果和语义评价信号。</p></article> : <>
          <section className="attribution-grid">
            <article className="panel suspect-card">
              <div className="panel-head"><div><span className="eyebrow">Primary suspect</span><h2>首要可疑 Span</h2></div><span className="heuristic-badge">规则基线</span></div>
              <div className="suspect-body"><span className={`span-kind kind-${attributedSpan?.kind ?? 'workflow'}`}>{attributedSpan ? (() => { const Icon = kindIcon[attributedSpan.kind]; return <Icon size={19} />; })() : <AlertTriangle size={19} />}</span><div><strong>{attributedSpan?.name ?? 'Unknown span'}</strong><code>{attributedSpan?.id}</code><p>{attributedSpan?.error ?? '该 Span 的错误状态和时延信号在候选项中得分最高。'}</p></div></div>
              <div className="score-row"><span>启发式分数</span><div><i style={{ width: `${(attribution.score ?? 0) * 100}%` }} /></div><strong>{((attribution.score ?? 0) * 100).toFixed(0)}</strong></div>
              <button className="text-action" onClick={() => { if (attributedSpan) setSelectedSpanId(attributedSpan.id); setView('replay'); }}>在时间线中定位 →</button>
            </article>
            <article className="panel propagation-card">
              <div className="panel-head"><div><span className="eyebrow">Propagation path</span><h2>错误传播路径</h2></div><GitBranch size={18} /></div>
              <div className="propagation-list">{pathSpans.map((span, index) => <div key={span.id}><i className={`kind-${span.kind}`}><span>{index + 1}</span></i><p><strong>{span.name}</strong><small>{span.agent} · {span.kind}</small></p>{index < pathSpans.length - 1 && <em />}</div>)}</div>
            </article>
          </section>
          <article className="panel evidence-panel">
            <div className="panel-head"><div><span className="eyebrow">Evidence ranking</span><h2>候选证据</h2></div><span className="result-count">{attribution.evidence.length} 条信号</span></div>
            <div className="evidence-list">{attribution.evidence.map((item, index) => { const span = trace.spans.find((candidate) => candidate.id === item.spanId); return <button key={item.spanId} onClick={() => { setSelectedSpanId(item.spanId); setView('replay'); }}><span>{index + 1}</span><p><strong>{span?.name ?? item.spanId}</strong><small>{item.observation}</small></p><i>{item.signal}</i><b>{item.score === null ? '—' : `${(item.score * 100).toFixed(0)}`}</b></button>; })}</div>
          </article>
        </>}
      </section>}

      {annotationOpen && <div className="dialog-backdrop" onMouseDown={() => setAnnotationOpen(false)}><section className="modal-card annotation-modal" onMouseDown={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-label="人工标注 Ground Truth"><div className="modal-head"><div><span className="eyebrow">Ground truth</span><h2>人工确认根因</h2></div><button className="icon-button" onClick={() => setAnnotationOpen(false)} aria-label="关闭"><X size={18} /></button></div><div className="annotation-warning"><AlertTriangle size={16} /><span>请根据 Trace 证据独立判断，不要仅复制自动候选。</span></div><label className="field"><span>根因 Span</span><select value={labelSpanId} onChange={(event) => setLabelSpanId(event.target.value)}>{trace.spans.map((span) => <option value={span.id} key={span.id}>{span.name} · {span.agent}</option>)}</select></label><label className="field"><span>失败类型</span><select value={failureType} onChange={(event) => setFailureType(event.target.value as GroundTruthLabel['failureType'])}><option value="tool_failure">工具失败</option><option value="llm_failure">LLM 失败</option><option value="handoff_failure">Agent Handoff 失败</option><option value="workflow_failure">工作流失败</option><option value="other">其他</option></select></label><label className="field"><span>证据说明</span><textarea value={labelNote} onChange={(event) => setLabelNote(event.target.value)} placeholder="记录支持该判断的日志、错误、时序或上下文证据…" /></label><p className="form-note">标签只保存到当前浏览器 localStorage；正式实验应记录标注者、盲评流程和数据版本。</p><div className="modal-actions"><button className="button secondary" onClick={() => setAnnotationOpen(false)}>取消</button><button className="button primary" disabled={!labelSpanId} onClick={saveGroundTruth}><FileCheck2 size={15} />保存人工标签</button></div></section></div>}
    </div>
  );
}
