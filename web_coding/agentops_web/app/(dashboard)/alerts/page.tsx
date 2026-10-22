import { AlertsWorkspace } from '@/components/alerts-workspace';
import { getAlertRules } from '@/lib/data-source';

export default async function AlertsPage() {
  return <AlertsWorkspace initialRules={await getAlertRules()} />;
}
