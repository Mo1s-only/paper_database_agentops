import { EvaluationWorkspace } from '@/components/evaluation-workspace';
import { getTraces } from '@/lib/data-source';

export default async function EvaluationsPage() {
  return <EvaluationWorkspace traces={await getTraces()} />;
}
