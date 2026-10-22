'use client';

import {
  Activity, ArrowDownUp, Bookmark, Bot, ChevronLeft, ChevronRight, CircleDollarSign,
  Download, ExternalLink, Filter, Search, TriangleAlert, Wrench, X,
} from 'lucide-react';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { useDashboard } from './dashboard-context';
import { EmptyState, PageHeader, StatusBadge } from './ui';
import type { Trace, TraceStatus } from '@/lib/types';
import { formatCompact, formatCost, formatDateTime, formatDuration } from '@/lib/format';
import { calculateTraceStats } from '@/lib/trace-stats';

type SortKey = 'startedAt' | 'durationMs' | 'cost' | 'tokens';

export function TraceExplorer({ traces }: { traces: Trace[] }) {
  const { selectedProjectId, timeRange, setTimeRange } = useDashboard();
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<'all' | TraceStatus>('all');
  const [sort, setSort] = useState<SortKey>('startedAt');
  const [page, setPage] = useState(1);
  const [bookmarks, setBookmarks] = useState<string[]>([]);
  const [bookmarkedOnly, setBookmarkedOnly] = useState(false);
  const [selectedTrace, setSelectedTrace] = useState<Trace | null>(null);
  const pageSize = 5;

  useEffect(() => {
    try { setBookmarks(JSON.parse(window.localStorage.getItem('agentops-bookmarks') ?? '[]')); } catch { setBookmarks([]); }
  }, []);

  const toggleBookmark = (id: string) => {
    setBookmarks((current) => {
      const next = current.includes(id) ? current.filter((item) => item !== id) : [...current, id];
      window.localStorage.setItem('agentops-bookmarks', JSON.stringify(next));
      return next;
    });
  };

  const filtered = useMemo(() => traces
    .filter((trace) => selectedProjectId === 'all' || trace.projectId === selectedProjectId)
    .filter((trace) => status === 'all' || trace.status === status)
    .filter((trace) => !bookmarkedOnly || bookmarks.includes(trace.id))
    .filter((trace) => `${trace.name} ${trace.id} ${trace.tags.join(' ')}`.toLowerCase().includes(query.toLowerCase()))
    .sort((a, b) => sort === 'startedAt'
      ? new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime()
      : b[sort] - a[sort]), [traces, selectedProjectId, status, bookmarkedOnly, bookmarks, query, sort]);

  useEffect(() => setPage(1), [query, status, selectedProjectId, bookmarkedOnly]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const visible = filtered.slice((page - 1) * pageSize, page * pageSize);
  const summary = useMemo(() => calculateTraceStats(filtered), [filtered]);

  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSelectedTrace(null);
    };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, []);

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(filtered, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = 'agentops-traces.json'; anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <PageHeader eyebrow="Observability / Traces" title="Trace 探索器" description="检索、比较并下钻每一次智能体执行。" actions={<><label className="select-control"><span>时间范围</span><select value={timeRange} onChange={(event) => setTimeRange(event.target.value)}><option value="24h">24 小时</option><option value="7d">7 天</option><option value="30d">30 天</option></select></label><button className="button secondary" onClick={exportJson}><Download size={16} />导出 JSON</button></>} />

      <section className="trace-kpi-grid" aria-label="当前筛选结果摘要">
        <article><span className="tone-violet"><Activity size={16} /></span><div><small>Traces</small><strong>{summary.traces}</strong></div></article>
        <article><span className="tone-blue"><Bot size={16} /></span><div><small>LLM calls</small><strong>{summary.llmCalls}</strong></div></article>
        <article><span className="tone-amber"><Wrench size={16} /></span><div><small>Tool calls</small><strong>{summary.toolCalls}</strong></div></article>
        <article><span className="tone-red"><TriangleAlert size={16} /></span><div><small>Error spans</small><strong>{summary.errors}</strong></div></article>
        <article><span className="tone-green"><CircleDollarSign size={16} /></span><div><small>Tokens / cost</small><strong>{formatCompact(summary.tokens)} · {formatCost(summary.cost)}</strong></div></article>
      </section>

      <section className="panel trace-panel">
        <div className="trace-toolbar">
          <label className="search-field"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索 Trace 名称、ID 或标签" />{query && <button onClick={() => setQuery('')} aria-label="清空搜索"><X size={15} /></button>}</label>
          <label className="compact-select"><Filter size={15} /><select value={status} onChange={(event) => setStatus(event.target.value as typeof status)}><option value="all">全部状态</option><option value="ok">成功</option><option value="error">错误</option><option value="running">运行中</option></select></label>
          <label className="compact-select"><ArrowDownUp size={15} /><select value={sort} onChange={(event) => setSort(event.target.value as SortKey)}><option value="startedAt">最新开始</option><option value="durationMs">耗时最高</option><option value="cost">成本最高</option><option value="tokens">Token 最多</option></select></label>
          <button className={`bookmark-filter ${bookmarkedOnly ? 'active' : ''}`} onClick={() => setBookmarkedOnly((value) => !value)}><Bookmark size={16} fill={bookmarkedOnly ? 'currentColor' : 'none'} />收藏</button>
          <span className="result-count">{filtered.length} 条结果</span>
        </div>

        {visible.length ? (
          <div className="table-scroll">
            <table className="data-table traces-table">
              <thead><tr><th aria-label="收藏" /><th>Trace</th><th>状态</th><th>时间</th><th>耗时</th><th>成本</th><th>Spans</th><th>Tokens</th><th aria-label="快速查看" /></tr></thead>
              <tbody>{visible.map((trace) => (
                <tr key={trace.id}>
                  <td><button className={`bookmark-button ${bookmarks.includes(trace.id) ? 'active' : ''}`} onClick={() => toggleBookmark(trace.id)} aria-label="收藏 Trace"><Bookmark size={16} fill={bookmarks.includes(trace.id) ? 'currentColor' : 'none'} /></button></td>
                  <td><Link className="trace-name" href={`/traces/${trace.id}`}><span>{trace.name}</span><code>{trace.id}</code><div className="tag-row">{trace.tags.slice(0, 2).map((tag) => <i key={tag}>{tag}</i>)}</div></Link></td>
                  <td><StatusBadge status={trace.status} /></td>
                  <td className="muted-cell">{formatDateTime(trace.startedAt)}</td>
                  <td><div className="duration-cell"><span><i style={{ width: `${Math.min(100, Math.max(8, trace.durationMs / 450))}%` }} /></span>{formatDuration(trace.durationMs)}</div></td>
                  <td>{formatCost(trace.cost)}</td><td>{trace.spans.length}</td><td>{formatCompact(trace.tokens)}</td>
                  <td><button className="quick-view-button" onClick={() => setSelectedTrace(trace)} aria-label={`快速查看 ${trace.name}`}><ChevronRight size={17} /></button></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : <EmptyState icon={Search} title="没有匹配的 Trace" description="尝试清空关键词、状态筛选或项目筛选。" />}

        <div className="pagination"><span>第 {page} / {pageCount} 页</span><div><button disabled={page === 1} onClick={() => setPage((value) => value - 1)}><ChevronLeft size={16} /></button><button disabled={page === pageCount} onClick={() => setPage((value) => value + 1)}><ChevronRight size={16} /></button></div></div>
      </section>

      {selectedTrace && <>
        <button className="drawer-scrim" onClick={() => setSelectedTrace(null)} aria-label="关闭快速详情" />
        <aside className="trace-drawer" role="dialog" aria-modal="true" aria-label="Trace 快速详情">
          <div className="drawer-head"><div><span className="eyebrow">Quick inspect</span><h2>{selectedTrace.name}</h2><code>{selectedTrace.id}</code></div><button className="icon-button" onClick={() => setSelectedTrace(null)} aria-label="关闭"><X size={18} /></button></div>
          <div className="drawer-meta"><StatusBadge status={selectedTrace.status} /><span>{formatDateTime(selectedTrace.startedAt)}</span><span>{formatDuration(selectedTrace.durationMs)}</span></div>
          <div className="drawer-stats">
            <div><span>LLM calls</span><strong>{selectedTrace.spans.filter((span) => span.kind === 'llm').length}</strong></div>
            <div><span>Tool calls</span><strong>{selectedTrace.spans.filter((span) => span.kind === 'tool').length}</strong></div>
            <div><span>Tokens</span><strong>{formatCompact(selectedTrace.tokens)}</strong></div>
            <div><span>Cost</span><strong>{formatCost(selectedTrace.cost)}</strong></div>
          </div>
          <div className="drawer-section-head"><div><span className="eyebrow">Call tree</span><h3>执行摘要</h3></div><span>{selectedTrace.spans.length} spans</span></div>
          <div className="drawer-span-list">{selectedTrace.spans.map((span) => (
            <div key={span.id} className={`drawer-span status-${span.status}`} style={{ paddingLeft: `${14 + (span.parentId ? 18 : 0)}px` }}>
              <i /><div><strong>{span.name}</strong><span>{span.agent} · {span.kind}{span.model ? ` · ${span.model}` : ''}</span></div><small>{formatDuration(span.durationMs)}</small>
            </div>
          ))}</div>
          <div className="drawer-tags">{selectedTrace.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>
          <Link className="button primary drawer-open" href={`/traces/${selectedTrace.id}`}>打开完整回放 <ExternalLink size={15} /></Link>
        </aside>
      </>}
    </>
  );
}
