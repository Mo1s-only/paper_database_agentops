import { OverviewDashboard } from '@/components/overview-dashboard';
import { getTraces } from '@/lib/data-source';

export default async function OverviewPage() {
  return <OverviewDashboard traces={await getTraces()} />;
}
