import { AlertsWorkspace } from '@/components/alerts-workspace';
import { getAlertState } from '@/lib/data-source';

export default async function AlertsPage() {
  const state = await getAlertState();
  return <AlertsWorkspace initialRules={state.rules} initialRevision={state.revision} />;
}
