'use client';

import { Check, Copy, FolderKanban, MoreHorizontal, Plus, RotateCw, Search, X } from 'lucide-react';
import { useState } from 'react';
import { EmptyState, PageHeader } from './ui';
import type { Project } from '@/lib/types';

export function ProjectsWorkspace({ initialProjects }: { initialProjects: Project[] }) {
  const [projects, setProjects] = useState(initialProjects);
  const [query, setQuery] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState('');
  const [environment, setEnvironment] = useState<Project['environment']>('development');
  const [copied, setCopied] = useState('');
  const filtered = projects.filter((project) => project.name.toLowerCase().includes(query.toLowerCase()));

  const createProject = (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    const id = name.trim().toLowerCase().replace(/[^a-z0-9\u4e00-\u9fa5]+/g, '-');
    setProjects((current) => [...current, { id, name: name.trim(), environment, apiKeyHint: 'aop_••••NEW1', traces24h: 0 }]);
    setName(''); setCreateOpen(false);
  };
  const copyKey = async (project: Project) => { await navigator.clipboard.writeText(project.apiKeyHint); setCopied(project.id); window.setTimeout(() => setCopied(''), 1000); };

  return <>
    <PageHeader eyebrow="Workspace / Projects" title="项目管理" description="隔离环境、API Key 与观测数据边界。" actions={<button className="button primary" onClick={() => setCreateOpen(true)}><Plus size={16} />新建项目</button>} />
    <div className="project-toolbar"><label className="search-field"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索项目" /></label><span>{projects.length} 个项目</span></div>
    {filtered.length ? <section className="project-grid">{filtered.map((project) => <article className="project-card" key={project.id}>
      <div className="project-card-head"><div className={`project-icon env-${project.environment}`}><FolderKanban size={20} /></div><button className="icon-button" aria-label="项目菜单"><MoreHorizontal size={18} /></button></div>
      <h2>{project.name}</h2><code>{project.id}</code>
      <div className="project-meta"><span className={`environment env-${project.environment}`}><i />{project.environment}</span><span>{project.traces24h} traces / 24h</span></div>
      <div className="key-row"><span>API Key</span><code>{project.apiKeyHint}</code><button onClick={() => copyKey(project)}>{copied === project.id ? <Check size={14} /> : <Copy size={14} />}</button><button title="轮换密钥"><RotateCw size={14} /></button></div>
    </article>)}</section> : <EmptyState icon={Search} title="没有匹配的项目" description="更换关键词或创建一个新项目。" />}

    {createOpen && <div className="dialog-backdrop" onMouseDown={() => setCreateOpen(false)}><form className="modal-card" onMouseDown={(event) => event.stopPropagation()} onSubmit={createProject}><div className="modal-head"><div><span className="eyebrow">New project</span><h2>创建观测项目</h2></div><button type="button" className="icon-button" onClick={() => setCreateOpen(false)}><X size={18} /></button></div><label className="field"><span>项目名称</span><input autoFocus value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：Production Copilot" required /></label><label className="field"><span>运行环境</span><select value={environment} onChange={(event) => setEnvironment(event.target.value as Project['environment'])}><option value="development">development</option><option value="staging">staging</option><option value="production">production</option></select></label><p className="form-note">演示模式下项目只保存在当前页面状态；接入后端后由 API 持久化。</p><div className="modal-actions"><button type="button" className="button secondary" onClick={() => setCreateOpen(false)}>取消</button><button className="button primary" type="submit">创建项目</button></div></form></div>}
  </>;
}
