import { ProjectsWorkspace } from '@/components/projects-workspace';
import { getProjects } from '@/lib/data-source';

export default async function ProjectsPage() {
  return <ProjectsWorkspace initialProjects={await getProjects()} />;
}
