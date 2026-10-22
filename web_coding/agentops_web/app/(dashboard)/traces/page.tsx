import { TraceExplorer } from '@/components/trace-explorer';
import { getTraces } from '@/lib/data-source';

export default async function TracesPage() {
  return <TraceExplorer traces={await getTraces()} />;
}
