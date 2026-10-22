import { MetricsWorkspace } from '@/components/metrics-workspace';
import { getTraces } from '@/lib/data-source';

export default async function MetricsPage() {
  return <MetricsWorkspace traces={await getTraces()} />;
}
