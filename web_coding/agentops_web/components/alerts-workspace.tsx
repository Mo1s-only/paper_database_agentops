'use client';

import { BellRing, CheckCircle2, CircleDollarSign, ClockAlert, Mail, Plus, Save, Webhook } from 'lucide-react';
import { useState } from 'react';
import { PageHeader } from './ui';
import type { AlertRule } from '@/lib/types';
import { formatDuration } from '@/lib/format';

const metricMeta = {
  error_rate: { label: 'Trace 错误率', icon: CheckCircle2, suffix: '%' },
  latency_p95: { label: 'P95 延迟', icon: ClockAlert, suffix: '' },
  daily_cost: { label: '每日成本', icon: CircleDollarSign, suffix: ' USD' },
};

export function AlertsWorkspace({ initialRules }: { initialRules: AlertRule[] }) {
  const [rules, setRules] = useState(initialRules);
  const [saved, setSaved] = useState(false);
  const update = (id: string, patch: Partial<AlertRule>) => setRules((current) => current.map((rule) => rule.id === id ? { ...rule, ...patch } : rule));
  const save = () => { setSaved(true); window.setTimeout(() => setSaved(false), 1300); };

  return <>
    <PageHeader eyebrow="Reliability / Alerts" title="告警策略" description="在失败扩大之前捕获异常率、延迟和成本偏移。" actions={<button className="button primary" onClick={save}><Save size={16} />{saved ? '已保存' : '保存策略'}</button>} />
    <section className="alert-banner"><div><BellRing size={20} /></div><p><strong>2 条策略正在监控</strong><span>评估窗口为 5 分钟；生产接入后可发送邮件或 Webhook。</span></p><button className="button secondary"><Plus size={16} />新建策略</button></section>
    <section className="alerts-list">{rules.map((rule) => { const meta = metricMeta[rule.metric]; const Icon = meta.icon; return <article className={`alert-rule ${rule.enabled ? '' : 'disabled'}`} key={rule.id}>
      <div className="alert-rule-icon"><Icon size={19} /></div><div className="alert-rule-title"><strong>{rule.name}</strong><span>{meta.label}</span></div>
      <div className="condition"><span>当</span><strong>{meta.label}</strong><span>{rule.operator}</span><label><input type="number" value={rule.threshold} onChange={(event) => update(rule.id, { threshold: Number(event.target.value) })} />{rule.metric === 'latency_p95' ? formatDuration(rule.threshold) : meta.suffix}</label></div>
      <div className="channel">{rule.channel === 'email' ? <Mail size={15} /> : <Webhook size={15} />}{rule.channel}</div>
      <label className="switch"><input type="checkbox" checked={rule.enabled} onChange={(event) => update(rule.id, { enabled: event.target.checked })} /><span /></label>
    </article>; })}</section>
  </>;
}
