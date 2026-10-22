'use client';

import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { Project } from '@/lib/types';

type Theme = 'dark' | 'light';

interface DashboardContextValue {
  projects: Project[];
  selectedProjectId: string;
  setSelectedProjectId: (id: string) => void;
  timeRange: string;
  setTimeRange: (value: string) => void;
  theme: Theme;
  toggleTheme: () => void;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function DashboardProvider({ projects, children }: { projects: Project[]; children: React.ReactNode }) {
  const [selectedProjectId, setSelectedProjectId] = useState('all');
  const [timeRange, setTimeRange] = useState('24h');
  const [theme, setTheme] = useState<Theme>('dark');

  useEffect(() => {
    const saved = window.localStorage.getItem('agentops-theme') as Theme | null;
    const next = saved === 'light' ? 'light' : 'dark';
    setTheme(next);
    document.documentElement.dataset.theme = next;
  }, []);

  const toggleTheme = () => {
    setTheme((current) => {
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = next;
      window.localStorage.setItem('agentops-theme', next);
      return next;
    });
  };

  const value = useMemo(
    () => ({ projects, selectedProjectId, setSelectedProjectId, timeRange, setTimeRange, theme, toggleTheme }),
    [projects, selectedProjectId, timeRange, theme],
  );

  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}

export function useDashboard() {
  const value = useContext(DashboardContext);
  if (!value) throw new Error('useDashboard must be used within DashboardProvider');
  return value;
}
