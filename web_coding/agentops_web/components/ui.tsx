import type { LucideIcon } from 'lucide-react';
import { ArrowDownRight, ArrowUpRight } from 'lucide-react';

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: string; actions?: React.ReactNode }) {
  return (
    <div className="page-header">
      <div>{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h1>{title}</h1>{description && <p>{description}</p>}</div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function StatCard({ label, value, change, trend = 'up', icon: Icon, tone = 'violet' }: { label: string; value: string; change?: string; trend?: 'up' | 'down'; icon: LucideIcon; tone?: string }) {
  return (
    <article className="stat-card">
      <div className={`stat-icon tone-${tone}`}><Icon size={18} /></div>
      <div className="stat-copy"><span>{label}</span><strong>{value}</strong></div>
      {change && <div className={`stat-change ${trend}`}>{trend === 'up' ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}{change}</div>}
    </article>
  );
}

export function StatusBadge({ status }: { status: 'ok' | 'error' | 'running' }) {
  const labels = { ok: '成功', error: '错误', running: '运行中' };
  return <span className={`status status-${status}`}><i />{labels[status]}</span>;
}

export function EmptyState({ title, description, icon: Icon }: { title: string; description: string; icon: LucideIcon }) {
  return <div className="empty-state"><div><Icon size={22} /></div><h3>{title}</h3><p>{description}</p></div>;
}
