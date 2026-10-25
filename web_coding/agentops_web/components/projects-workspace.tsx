'use client';
import { ArrowUpRight, FolderKanban, Pencil, Plus, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { EmptyState, PageHeader } from './ui';
import type { Project } from '@/lib/types';
import { useDashboard } from './dashboard-context';
import { useToast } from './toast';
import { Modal } from './modal';
import { readStored } from '@/lib/browser-storage';

export function ProjectsWorkspace({ initialProjects: _initialProjects }: { initialProjects: Project[] }) {
  const { projects, saveProject, setSelectedProjectId, dataMode } = useDashboard();
  const router = useRouter();
  const toast = useToast();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Project | null>(null);
  const [name, setName] = useState('');
  const [environment, setEnvironment] = useState<Project['environment']>('development');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [legacy, setLegacy] = useState<Project[]>([]);
  useEffect(() => { setLegacy(readStored<Project[]>('agentops-projects-v1', [], (v): v is Project[] => Array.isArray(v) && v.every((p) => p && typeof p.id === 'string' && typeof p.name === 'string' && ['production', 'staging', 'development'].includes(p.environment)))); }, []);
  const filtered = projects.filter((project) => `${project.name} ${project.id}`.toLowerCase().includes(query.toLowerCase()));
  function show(project: Project | null) { setEditing(project); setName(project?.name ?? ''); setEnvironment(project?.environment ?? 'development'); setError(''); setOpen(true); }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim() || projects.some((p) => p.id !== editing?.id && p.name.toLowerCase() === name.trim().toLowerCase())) { setError('请输入不重复的项目名称。'); return; }
    const project = { id: editing?.id ?? `prj_${crypto.randomUUID()}`, revision: editing?.revision ?? 0, name: name.trim(), environment, apiKeyHint: editing?.apiKeyHint ?? '尚未配置', traces24h: editing?.traces24h ?? 0 };
    setSaving(true);
    if (await saveProject(project)) { setOpen(false); setLegacy((rows) => rows.filter((p) => p.id !== project.id)); toast('项目已保存到本机数据库'); }
    setSaving(false);
  }
  return <>
    <PageHeader eyebrow="Workspace / Projects" title="项目管理" description="管理工作区中的应用与运行环境，快速进入项目的执行记录。" actions={dataMode === 'mock' && <button className="button primary" onClick={() => show(null)}><Plus size={16} />新建项目</button>} />
    <div className="data-scope"><FolderKanban size={14} /><span>{dataMode === 'mock' ? '项目配置保存在服务端 SQLite，刷新或更换浏览器后仍可读取。' : '远程项目由服务端管理，本页提供只读查看。'}</span></div>
    {dataMode === 'mock' && legacy.length > 0 && <div className="migration-banner"><strong>检测到旧浏览器项目</strong><p>旧数据仍保留，可逐项载入并确认保存；不会自动覆盖服务端配置。</p><div>{legacy.map((p) => <button className="button secondary" key={p.id} onClick={() => show({ ...p, revision: projects.find((current) => current.id === p.id)?.revision ?? 0 })}>载入 {p.name}</button>)}</div></div>}
    <div className="project-toolbar"><label className="search-field"><Search size={17} /><input aria-label="搜索项目" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索项目名称或 ID" /></label><span>{filtered.length} / {projects.length} 个项目</span></div>
    {filtered.length ? <section className="project-grid">{filtered.map((project) => <article className="project-card" key={project.id}>
      <div className="project-card-head"><div className={`project-icon env-${project.environment}`}><FolderKanban size={20} /></div>{dataMode === 'mock' && <button className="icon-button" aria-label={`编辑 ${project.name}`} onClick={() => show(project)}><Pencil size={16} /></button>}</div>
      <h2>{project.name}</h2><code className="project-id">{project.id}</code>
      <div className="project-meta"><span className={`environment env-${project.environment}`}><i />{project.environment}</span></div>
      <div className="project-card-footer"><span>工作区项目</span><button className="text-link" onClick={() => { setSelectedProjectId(project.id); router.push('/traces'); }}>查看 Traces <ArrowUpRight size={15} /></button></div>
    </article>)}</section> : <EmptyState icon={Search} title="没有匹配的项目" description="更换关键词或创建一个新项目。" />}
    {open && <Modal title={editing ? '编辑项目' : '创建观测项目'} onClose={() => { if (!saving) setOpen(false); }}><form onSubmit={save}>
      <label className="field"><span>项目名称</span><input autoFocus value={name} onChange={(event) => { setName(event.target.value); setError(''); }} placeholder="例如：Production Copilot" required maxLength={80} /></label>
      <label className="field"><span>运行环境</span><select value={environment} onChange={(event) => setEnvironment(event.target.value as Project['environment'])}><option value="development">Development</option><option value="staging">Staging</option><option value="production">Production</option></select></label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="modal-actions"><button type="button" className="button secondary" disabled={saving} onClick={() => setOpen(false)}>取消</button><button className="button primary" disabled={saving}>{saving ? '保存中…' : editing ? '保存更改' : '创建项目'}</button></div>
    </form></Modal>}
  </>;
}
