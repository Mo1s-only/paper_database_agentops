import { AppShell } from '@/components/app-shell';
import { DashboardProvider } from '@/components/dashboard-context';
import { getProjects, getDataMode, getReferenceTime } from '@/lib/data-source';
import { ToastProvider } from '@/components/toast';

export const dynamic = 'force-dynamic';

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const projects = await getProjects();
  return <ToastProvider><DashboardProvider projects={projects} dataMode={getDataMode()} referenceTime={getReferenceTime()}><AppShell>{children}</AppShell></DashboardProvider></ToastProvider>;
}
