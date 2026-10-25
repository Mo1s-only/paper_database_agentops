'use client';

import {
  Activity, Bell, ChartNoAxesCombined, ChevronDown, ChevronsLeft, ChevronsRight, Gauge,
  CheckCheck, CircleAlert, CloudCog, FlaskConical, FolderKanban, Github, Menu, Moon,
  PlugZap, Search, Settings, ShieldAlert, Sun, Timer, X,
} from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { AgentOpsLogo } from './logo';
import { useDashboard } from './dashboard-context';

const navigation = [
  { href: '/overview', label: '总览', icon: ChartNoAxesCombined },
  { href: '/traces', label: 'Traces', icon: Activity },
  { href: '/metrics', label: 'Metrics', icon: Gauge },
  { href: '/evaluations', label: '评测', icon: FlaskConical },
  { href: '/projects', label: '项目', icon: FolderKanban },
  { href: '/alerts', label: '告警', icon: ShieldAlert },
  { href: '/mcp', label: 'MCP', icon: PlugZap },
  { href: '/deploy', label: 'Deploy', icon: CloudCog },
];

const commands = [
  ...navigation,
  { href: '/settings', label: '设置与接入', icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { projects, selectedProjectId, setSelectedProjectId, theme, toggleTheme, dataMode } = useDashboard();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notificationsRead, setNotificationsRead] = useState(false);
  const [query, setQuery] = useState('');

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setCommandOpen((open) => !open);
      }
      if (event.key === 'Escape') {
        setCommandOpen(false);
        setNotificationsOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  useEffect(() => setMobileOpen(false), [pathname]);

  const filteredCommands = useMemo(
    () => commands.filter((item) => item.label.toLowerCase().includes(query.toLowerCase())),
    [query],
  );

  return (
    <div className={`app-frame ${collapsed ? 'sidebar-collapsed' : ''}`}>
      <a className="skip-link" href="#main-content">跳转到主要内容</a>
      <button className="mobile-menu" onClick={() => setMobileOpen(true)} aria-label="打开菜单"><Menu size={20} /></button>
      {mobileOpen && <button className="mobile-scrim" onClick={() => setMobileOpen(false)} aria-label="关闭菜单" />}
      <aside className={`sidebar ${mobileOpen ? 'mobile-open' : ''}`}>
        <div className="sidebar-head">
          <Link href="/overview"><AgentOpsLogo compact={collapsed} /></Link>
          <button className="icon-button mobile-close" onClick={() => setMobileOpen(false)} aria-label="关闭菜单"><X size={18} /></button>
        </div>

        {!collapsed && <><div className="workspace-label"><span>AW</span><div><strong>AgentOps Workspace</strong><small>{dataMode === 'mock' ? '本机持久化工作区' : '远程数据工作区'}</small></div></div><div className="nav-section-label">Workspace</div></>}
        <nav className="primary-nav" aria-label="主导航">
          {navigation.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <Link key={item.href} href={item.href} aria-current={active ? 'page' : undefined} className={`nav-item ${active ? 'active' : ''}`} title={collapsed ? item.label : undefined}>
                <Icon size={18} strokeWidth={1.8} />
                {!collapsed && <span>{item.label}</span>}
                {item.href === '/deploy' && !collapsed && <span className="nav-alpha">α</span>}
              </Link>
            );
          })}
        </nav>

        <div className="sidebar-spacer" />
        <div className="secondary-nav">
          <a className="nav-item" href="https://github.com/AgentOps-AI/agentops" target="_blank" rel="noreferrer" title="上游项目">
            <Github size={18} strokeWidth={1.8} />{!collapsed && <span>上游项目</span>}
          </a>
          <Link className={`nav-item ${pathname === '/settings' ? 'active' : ''}`} href="/settings" title="设置与接入">
            <Settings size={18} strokeWidth={1.8} />{!collapsed && <span>设置与接入</span>}
          </Link>
          <button className="nav-item collapse-button" onClick={() => setCollapsed((value) => !value)}>
            {collapsed ? <ChevronsRight size={18} /> : <ChevronsLeft size={18} />}
            {!collapsed && <span>收起侧栏</span>}
          </button>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="project-picker">
            <span className="project-dot" />
            <select value={selectedProjectId} onChange={(event) => setSelectedProjectId(event.target.value)} aria-label="选择项目">
              <option value="all">全部项目</option>
              {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
            <ChevronDown size={14} aria-hidden="true" />
          </div>
          <div className="topbar-actions">
            <span className={`connection-pill ${dataMode}`}><i />{dataMode === 'mock' ? '本地模式' : '远程模式'}</span>
            <button className="search-button" aria-label="搜索页面与命令" onClick={() => setCommandOpen(true)}>
              <Search size={16} /><span>搜索页面与命令</span><kbd>Ctrl K</kbd>
            </button>
            <button className="icon-button" onClick={toggleTheme} aria-label="切换主题">
              {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <button className="icon-button notification-button" aria-label="通知" aria-expanded={notificationsOpen} onClick={() => setNotificationsOpen((open) => !open)}><Bell size={18} />{!notificationsRead && <i />}</button>
            <div className="avatar" title="Research Operator">RO</div>
          </div>
        </header>
        <main className="page-content" id="main-content" tabIndex={-1}>{children}</main>
      </div>

      {commandOpen && (
        <div className="dialog-backdrop" onMouseDown={() => setCommandOpen(false)}>
          <section className="command-dialog" onMouseDown={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-label="搜索">
            <div className="command-input"><Search size={18} /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="输入页面名称…" /></div>
            <div className="command-results">
              <span className="eyebrow">快速跳转</span>
              {filteredCommands.map((item) => {
                const Icon = item.icon;
                return <button key={item.href} onClick={() => { setCommandOpen(false); router.push(item.href); }}><Icon size={17} /><span>{item.label}</span><kbd>↵</kbd></button>;
              })}
              {!filteredCommands.length && <p className="empty-compact">没有匹配的页面</p>}
            </div>
          </section>
        </div>
      )}
      {notificationsOpen && <>
        <button className="notification-scrim" onClick={() => setNotificationsOpen(false)} aria-label="关闭通知" />
        <section className="notification-popover" aria-label="通知中心">
          <div className="notification-head"><div><span className="eyebrow">Activity</span><h2>通知</h2></div><button onClick={() => setNotificationsRead(true)}><CheckCheck size={14} />全部已读</button></div>
          <div className="notification-demo-label">演示通知 · 未连接推送服务</div>
          {dataMode === 'mock' ? <><Link href="/traces/tr_819ca7752bb1" onClick={() => setNotificationsOpen(false)} className={notificationsRead ? 'read' : ''}><span className="notification-icon error"><CircleAlert size={16} /></span><p><strong>示例：工具调用超时</strong><span>incident_root_cause_analysis</span><small>样本快照 · Multi-Agent Benchmark</small></p></Link><Link href="/metrics" onClick={() => setNotificationsOpen(false)} className={notificationsRead ? 'read' : ''}><span className="notification-icon latency"><Timer size={16} /></span><p><strong>示例：P95 延迟超过 30s</strong><span>查看当前样本的延迟分布</span><small>样本快照 · 演示规则</small></p></Link></> : <p className="empty-compact">尚未连接实时通知服务</p>}
          <div className="notification-foot"><Link href="/alerts" onClick={() => setNotificationsOpen(false)}>查看告警策略</Link></div>
        </section>
      </>}
    </div>
  );
}
