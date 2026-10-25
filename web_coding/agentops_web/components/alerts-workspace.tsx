'use client';
import { BellRing, Plus, Save, Pencil, Trash2, Mail, Webhook, ShieldCheck } from 'lucide-react';
import { useEffect, useState } from 'react';
import { PageHeader, EmptyState } from './ui';
import { Modal } from './modal';
import { useToast } from './toast';
import { useDashboard } from './dashboard-context';
import { readStored, writeStored } from '@/lib/browser-storage';
import { validAlertRules } from '@/lib/validation';
import type { AlertRule } from '@/lib/types';
import { writeApi } from '@/lib/api-client';

const metricMeta = { error_rate: { label: 'Trace 错误率', unit: '%' }, latency_p95: { label: 'P95 延迟', unit: 'ms' }, daily_cost: { label: '每日成本', unit: 'USD' } };
const newRule = (): AlertRule => ({ id: crypto.randomUUID(), name: '', metric: 'error_rate', operator: '>', threshold: 5, channel: 'email', enabled: true });
export function AlertsWorkspace({ initialRules, initialRevision }: { initialRules: AlertRule[]; initialRevision: number }) {
  const { dataMode } = useDashboard();
  const [rules, setRules] = useState(initialRules);
  const [draft, setDraft] = useState<AlertRule | null>(null);
  const [deleting, setDeleting] = useState<AlertRule | null>(null);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(initialRevision);
  const [saving, setSaving] = useState(false);
  const [legacy, setLegacy] = useState<AlertRule[] | null>(null);
  const toast = useToast();
  useEffect(() => { setRules(initialRules); setRevision(initialRevision); setDirty(false); }, [initialRules, initialRevision]);
  useEffect(() => { setLegacy(readStored<AlertRule[] | null>('agentops-alert-rules-v1', null, (v): v is AlertRule[] | null => v === null || validAlertRules(v))); }, []);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
  async function save() {
    if (!validAlertRules(rules)) { toast('策略中存在无效阈值。', true); return; }
    setSaving(true);
    try {
      const saved = await writeApi<{ rules: AlertRule[]; revision: number }>('/api/v1/alerts', { rules, revision }, 'PUT');
      setRules(saved.rules); setRevision(saved.revision); setDirty(false); toast('全部策略已保存到本机数据库');
    } catch (error) { toast(error instanceof Error ? error.message : '保存失败', true); }
    finally { setSaving(false); }
  }
  function apply(event: React.FormEvent) {
    event.preventDefault();
    if (!draft || !validAlertRules([draft]) || rules.some((r) => r.id !== draft.id && r.name.toLowerCase() === draft.name.trim().toLowerCase())) { setError('请检查名称和阈值；错误率范围为 0–100%。'); return; }
    setRules([...rules.filter((r) => r.id !== draft.id), { ...draft, name: draft.name.trim() }]); setDirty(true); setDraft(null);
  }
  return <>
    <PageHeader eyebrow="Reliability / Alert policies" title="告警策略" description="为错误率、执行延迟和模型成本设置清晰的响应边界。" actions={dataMode === 'mock' && <><button className="button secondary" disabled={saving} onClick={() => { setDraft(newRule()); setError(''); }}><Plus size={16} />新建策略</button><button className="button primary" disabled={!dirty || saving} onClick={save}><Save size={16} />{saving ? '保存中…' : `保存策略${dirty ? ' · 有更改' : ''}`}</button></>} />
    <section className="policy-summary"><div><ShieldCheck size={22} /><p><strong>{rules.filter((r) => r.enabled).length} 条启用配置</strong><span>共 {rules.length} 条策略 · {dataMode === 'mock' ? `SQLite 持久化 · 版本 ${revision}` : '远程只读配置'}</span></p></div><span className="heuristic-badge">通知通道待接入</span></section>
    {dataMode === 'mock' && legacy !== null && <div className="migration-banner"><strong>旧浏览器策略可迁移</strong><p>载入后将替换当前草稿，需点击“保存策略”才写入服务端。旧浏览器记录不会删除。</p><button className="button secondary" disabled={saving} onClick={() => { setRules(legacy); setDirty(true); setLegacy(null); }}>载入旧策略草稿</button></div>}
    <p className="policy-note">这里管理策略配置。持续评估与邮件 / Webhook 投递需连接告警服务。</p>
    {rules.length ? <section className="policy-grid">{rules.map((rule) => <article className={`panel policy-card ${rule.enabled ? '' : 'disabled'}`} key={rule.id}>
      <div className="policy-card-head"><span className="policy-glyph"><BellRing size={18} /></span><label className="switch"><input type="checkbox" disabled={dataMode === 'remote' || saving} aria-label={`启用 ${rule.name}`} checked={rule.enabled} onChange={(e) => { setRules(rules.map((r) => r.id === rule.id ? { ...r, enabled: e.target.checked } : r)); setDirty(true); }} /><span /></label></div>
      <h2>{rule.name}</h2><p>{metricMeta[rule.metric].label}</p><div className="policy-threshold"><span>&gt;</span><strong>{rule.threshold.toLocaleString()}</strong><small>{metricMeta[rule.metric].unit}</small></div>
      <div className="policy-card-foot"><span>{rule.channel === 'email' ? <Mail size={14} /> : <Webhook size={14} />}{rule.channel}</span>{dataMode === 'mock' && <div><button className="icon-button" disabled={saving} aria-label={`编辑策略 ${rule.name}`} onClick={() => { setDraft({ ...rule }); setError(''); }}><Pencil size={14} /></button><button className="icon-button" disabled={saving} aria-label={`删除策略 ${rule.name}`} onClick={() => setDeleting(rule)}><Trash2 size={14} /></button></div>}</div>
    </article>)}</section> : <EmptyState icon={BellRing} title="尚未设置策略" description="添加第一条错误率、延迟或成本策略。" />}
    {draft && <Modal title={rules.some((r) => r.id === draft.id) ? '编辑告警策略' : '新建告警策略'} onClose={() => setDraft(null)}><form onSubmit={apply}>
      <label className="field"><span>策略名称</span><input autoFocus required maxLength={80} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></label>
      <label className="field"><span>监控指标</span><select value={draft.metric} onChange={(e) => setDraft({ ...draft, metric: e.target.value as AlertRule['metric'] })}>{Object.entries(metricMeta).map(([id, item]) => <option key={id} value={id}>{item.label}</option>)}</select></label>
      <label className="field"><span>大于阈值（{metricMeta[draft.metric].unit}）</span><input type="number" required min={0} max={draft.metric === 'error_rate' ? 100 : undefined} step="any" value={Number.isNaN(draft.threshold) ? '' : draft.threshold} onChange={(e) => setDraft({ ...draft, threshold: e.target.valueAsNumber })} /></label>
      <label className="field"><span>通知通道类型</span><select value={draft.channel} onChange={(e) => setDraft({ ...draft, channel: e.target.value as AlertRule['channel'] })}><option value="email">Email</option><option value="webhook">Webhook</option></select></label>
      {error && <p className="form-error" role="alert">{error}</p>}<div className="modal-actions"><button className="button secondary" type="button" onClick={() => setDraft(null)}>取消</button><button className="button primary">应用到草稿</button></div>
    </form></Modal>}
    {deleting && <Modal title="删除告警策略" onClose={() => setDeleting(null)}><p>确定删除「{deleting.name}」？保存策略后生效。</p><div className="modal-actions"><button className="button secondary" onClick={() => setDeleting(null)}>取消</button><button className="button danger" onClick={() => { setRules(rules.filter((r) => r.id !== deleting.id)); setDirty(true); setDeleting(null); }}>删除策略</button></div></Modal>}
  </>;
}
