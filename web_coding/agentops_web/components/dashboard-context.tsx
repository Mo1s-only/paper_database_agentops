'use client';

import { createContext, useContext, useEffect, useState } from 'react';
import type { Project } from '@/lib/types';
import { readStored, writeStored } from '@/lib/browser-storage';
import { useToast } from './toast';
import { writeApi } from '@/lib/api-client';
import { useRouter } from 'next/navigation';

type Theme = 'dark' | 'light';

interface DashboardContextValue {
  projects: Project[];
  saveProject: (project: Project) => Promise<boolean>;
  dataMode: 'mock' | 'remote';
  referenceTime: number;
  selectedProjectId: string;
  setSelectedProjectId: (id: string) => void;
  timeRange: string;
  traceSource: string;
  setTraceSource: (value: string) => void;
  setTimeRange: (value: string) => void;
  theme: Theme;
  toggleTheme: () => void;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function DashboardProvider({ projects: initialProjects, dataMode, referenceTime, children }: { projects: Project[]; dataMode: 'mock' | 'remote'; referenceTime: number; children: React.ReactNode }) {
  const [projects, setProjects] = useState<Project[]>(initialProjects);
  const router = useRouter();
  const toast = useToast();
  useEffect(() => { setProjects(initialProjects); }, [initialProjects]);
  const [selectedProjectId, setSelectedProjectId] = useState('all');
  const [timeRange, setTimeRange] = useState('24h');
  const [traceSource, setTraceSource] = useState('all');
  const [theme, setTheme] = useState<Theme>('dark');

  useEffect(() => {
    const selected = readStored('agentops-project-selection', 'all', (value): value is string => typeof value === 'string');
    setSelectedProjectId(initialProjects.some((p) => p.id === selected) ? selected : 'all');
    setTimeRange(readStored('agentops-time-range', '24h', (value): value is string => typeof value === 'string' && ['1h', '24h', '7d', '30d', 'all'].includes(value)));
    setTraceSource(dataMode === 'remote' ? 'all' : readStored('agentops-trace-source', 'all', (v): v is string => typeof v === 'string' && ['all', 'demo', 'imported'].includes(v)));
    let saved: string | null = null;
    try { saved = window.localStorage.getItem('agentops-theme'); } catch { /* Fall back to dark. */ }
    const next = saved === 'light' ? 'light' : 'dark';
    setTheme(next);
    document.documentElement.dataset.theme = next;
  }, [initialProjects, dataMode]);

  const saveProject = async (project: Project) => {
    if (dataMode !== 'mock') { toast('远程项目请在后端管理平台修改。', true); return false; }
    try {
      const saved = await writeApi<Project>('/api/v1/projects', project, 'PUT');
      setProjects((current) => [...current.filter((p) => p.id !== saved.id), saved]); router.refresh(); return true;
    } catch (error) { toast(error instanceof Error ? error.message : '项目保存失败', true); return false; }
  };

  const toggleTheme = () => {
    setTheme((current) => {
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = next;
      try { window.localStorage.setItem('agentops-theme', next); } catch { /* Theme still applies for this visit. */ }
      return next;
    });
  };

  const value = { projects, saveProject, dataMode, referenceTime, selectedProjectId,
    traceSource, setTraceSource: (source: string) => { setTraceSource(source); writeStored('agentops-trace-source', source); },
    setSelectedProjectId: (id: string) => { setSelectedProjectId(id); writeStored('agentops-project-selection', id); },
    timeRange, setTimeRange: (range: string) => { setTimeRange(range); writeStored('agentops-time-range', range); }, theme, toggleTheme };

  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}

export function useDashboard() {
  const value = useContext(DashboardContext);
  if (!value) throw new Error('useDashboard must be used within DashboardProvider');
  return value;
}
