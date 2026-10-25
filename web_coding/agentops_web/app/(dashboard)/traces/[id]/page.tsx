import { notFound } from 'next/navigation';
import { TraceDetail } from '@/components/trace-detail';
import { getTrace, getLabels } from '@/lib/data-source';

export default async function TraceDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const trace = await getTrace(id);
  if (!trace) notFound();
  return <TraceDetail trace={trace} initialLabel={getLabels().find((label) => label.traceId === id) ?? null} />;
}
