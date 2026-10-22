import { AppShell } from '@/components/app-shell';
import { DashboardProvider } from '@/components/dashboard-context';
import { getProjects } from '@/lib/data-source';

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const projects = await getProjects();
  return <DashboardProvider projects={projects}><AppShell>{children}</AppShell></DashboardProvider>;
}
