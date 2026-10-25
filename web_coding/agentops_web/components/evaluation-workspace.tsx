'use client';

import {
  ArrowUpRight, Check, ClipboardCheck, Download, FileQuestion, FlaskConical,
  GitCompareArrows, Tags, TriangleAlert,
} from 'lucide-react';
import Link from 'next/link';
import { useMemo, useState } from 'react';
import { buildEvaluationRecords } from '@/lib/evaluation';
import type { GroundTruthLabel, Trace } from '@/lib/types';
import { useDashboard } from './dashboard-context';
import { PageHeader } from './ui';

const labelNames: Record<GroundTruthLabel['failureType'], string> = {
  tool_failure: '工具失败',
  llm_failure: 'LLM 失败',
  handoff_failure: 'Handoff 失败',
  workflow_failure: '工作流失败',
  other: '其他',
};

export function EvaluationWorkspace({ traces, labels }: { traces: Trace[]; labels: GroundTruthLabel[] }) {
  const { selectedProjectId, dataMode } = useDashboard();
  const [source, setSource] = useState('all');
  const [exported, setExported] = useState(false);

  const visibleTraces = useMemo(
    () => traces.filter((trace) => (selectedProjectId === 'all' || trace.projectId === selectedProjectId) && (source === 'all' || trace.provenance?.kind === source)),
    [selectedProjectId, traces, source],
  );
  const records = useMemo(() => buildEvaluationRecords(visibleTraces, labels), [labels, visibleTraces]);
  const labeled = records.filter((record) => record.groundTruth);
  const agreements = labeled.filter((record) => record.agreesWithHuman).length;
  const agreementRate = labeled.length ? agreements / labeled.length * 100 : null;
  const taxonomy = Object.entries(labelNames).map(([key, name]) => ({
    key,
    name,
    count: labeled.filter((record) => record.groundTruth?.failureType === key).length,
  })).filter((item) => item.count > 0);

  function exportDataset() {
    const payload = {
      schemaVersion: '0.1.0',
      exportedAt: new Date().toISOString(),
      scope: { projectId: selectedProjectId, dataMode, source },
      method: { name: 'transparent-rule-baseline', version: '0.1.0' },
      records: records.map((record) => ({
        traceId: record.trace.id,
        traceName: record.trace.name,
        provenance: record.trace.provenance ?? { kind: 'remote-unverified' },
        automaticAttribution: record.attribution,
        groundTruth: record.groundTruth,
        agreesWithHuman: record.agreesWithHuman,
      })),
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `agentops-evaluation-${new Date().toISOString().slice(0, 10)}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    setExported(true);
    window.setTimeout(() => setExported(false), 1800);
  }

  return <>
    <PageHeader
      eyebrow="Research / Evaluation"
      title="失败归因评测工作台"
      description="聚合失败 Trace、自动候选与人工 Ground Truth；把演示推断和可验证标签明确分开。"
      actions={<button className="button secondary" onClick={exportDataset}><Download size={15} />{exported ? '已导出' : '导出评测集'}</button>}
    />

    <div className="evaluation-boundary"><FlaskConical size={17} /><p><strong>研究协议草案 · AUTHOR_INPUT_NEEDED</strong><span>当前只验证数据结构和工作流。正式论文结论需要真实失败 Trace、盲评标注、裁决规则与冻结的数据版本。</span></p></div>
    {dataMode === 'mock' && <label className="select-control source-picker"><span>评测数据来源</span><select value={source} onChange={(e) => setSource(e.target.value)}><option value="all">全部来源（可能包含示例）</option><option value="imported">仅用户导入（未经独立验证）</option><option value="demo">仅示例数据</option></select></label>}

    <section className="evaluation-kpis">
      <article><span className="tone-red"><TriangleAlert size={18} /></span><p><small>失败 Trace</small><strong>{records.length}</strong><em>当前项目筛选</em></p></article>
      <article><span className="tone-violet"><GitCompareArrows size={18} /></span><p><small>自动候选</small><strong>{records.filter((record) => record.attribution.rootSpanId).length}</strong><em>规则基线 v0.1.0</em></p></article>
      <article><span className="tone-blue"><ClipboardCheck size={18} /></span><p><small>人工标签覆盖</small><strong>{`${labeled.length} / ${records.length}`}</strong><em>{dataMode === 'mock' ? '服务端保存 · 待独立复核' : '远程标签服务未接入'}</em></p></article>
      <article><span className="tone-green"><Check size={18} /></span><p><small>已标注样本一致率</small><strong>{agreementRate === null ? '待标注' : `${agreementRate.toFixed(0)}%`}</strong><em>{agreementRate === null ? '不将缺失标签计为 0%' : `n = ${labeled.length}`}</em></p></article>
    </section>

    <section className="evaluation-layout">
      <article className="panel evaluation-table-panel">
        <div className="panel-head"><div><span className="eyebrow">Comparison set</span><h2>失败 Trace 对照</h2></div><span className="local-data-badge">LOCAL DERIVED</span></div>
        {records.length ? <div className="table-scroll"><table className="data-table evaluation-table"><thead><tr><th>Trace</th><th>自动候选</th><th>Ground Truth</th><th>一致性</th><th /></tr></thead><tbody>{records.map((record) => {
          const automaticSpan = record.trace.spans.find((span) => span.id === record.attribution.rootSpanId);
          const humanSpan = record.trace.spans.find((span) => span.id === record.groundTruth?.rootSpanId);
          return <tr key={record.trace.id}>
            <td><Link className="trace-name" href={`/traces/${record.trace.id}`}><span>{record.trace.name}</span><code>{record.trace.id}</code><small>{record.trace.provenance?.kind === 'demo' ? '示例数据' : '未经独立验证的输入'}</small></Link></td>
            <td><div className="evaluation-candidate"><strong>{automaticSpan?.name ?? '无候选'}</strong><code>{record.attribution.rootSpanId ?? '—'} · {record.attribution.score === null ? '—' : record.attribution.score.toFixed(2)}</code></div></td>
            <td>{record.groundTruth ? <div className="evaluation-candidate human"><strong>{humanSpan?.name ?? record.groundTruth.rootSpanId}</strong><span>{labelNames[record.groundTruth.failureType]}</span></div> : <span className="label-needed"><FileQuestion size={14} />待人工标注</span>}</td>
            <td>{record.agreesWithHuman === null ? <span className="comparison-state pending">不可计算</span> : record.agreesWithHuman ? <span className="comparison-state agree">一致</span> : <span className="comparison-state disagree">分歧</span>}</td>
            <td><Link className="text-link" href={`/traces/${record.trace.id}`}>{record.groundTruth ? '复核' : '去标注'}<ArrowUpRight size={13} /></Link></td>
          </tr>;
        })}</tbody></table></div> : <div className="evaluation-empty"><Check size={22} /><strong>当前筛选没有失败 Trace</strong><span>切换到“全部项目”或接入包含失败样本的数据源。</span></div>}
      </article>

      <aside className="evaluation-side">
        <article className="panel protocol-card"><div className="panel-head"><div><span className="eyebrow">Protocol draft</span><h2>实验设计卡</h2></div></div><dl>
          <div><dt>研究问题</dt><dd>能否从 Trace 证据定位多智能体失败的首要根因 Span？</dd></div>
          <div><dt>基线</dt><dd><code>transparent-rule-baseline@0.1.0</code></dd></div>
          <div><dt>输入</dt><dd>Trace 拓扑、状态、错误、类型与延迟</dd></div>
          <div><dt>主指标</dt><dd>Root-span agreement（仅对已标注样本）</dd></div>
          <div><dt>边界</dt><dd>演示样本不可作为论文实验结果</dd></div>
        </dl><div className="protocol-status"><i />尚待冻结：标注指南、双人一致性、裁决与数据切分</div></article>
        <article className="panel taxonomy-card"><div className="panel-head"><div><span className="eyebrow">Human labels</span><h2>失败类型分布</h2></div><Tags size={16} /></div>{taxonomy.length ? <div className="taxonomy-list">{taxonomy.map((item) => <div key={item.key}><span>{item.name}</span><strong>{item.count}</strong></div>)}</div> : <div className="taxonomy-empty"><FileQuestion size={20} /><strong>暂无人工标签</strong><span>从失败 Trace 详情完成第一次独立标注后，这里才会生成分布。</span></div>}</article>
      </aside>
    </section>
  </>;
}
