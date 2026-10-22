export type TraceStatus = 'ok' | 'error' | 'running';
export type SpanKind = 'agent' | 'llm' | 'tool' | 'workflow';

export interface Project {
  id: string;
  name: string;
  environment: 'production' | 'staging' | 'development';
  apiKeyHint: string;
  traces24h: number;
}

export interface Span {
  id: string;
  parentId: string | null;
  name: string;
  kind: SpanKind;
  agent: string;
  model?: string;
  startedAt: string;
  durationMs: number;
  input: string;
  output: string;
  tokens: number;
  cost: number;
  status: TraceStatus;
  error?: string;
}

export interface Trace {
  id: string;
  projectId: string;
  name: string;
  startedAt: string;
  durationMs: number;
  status: TraceStatus;
  tokens: number;
  cost: number;
  tags: string[];
  spans: Span[];
}

export interface AlertRule {
  id: string;
  name: string;
  metric: 'error_rate' | 'latency_p95' | 'daily_cost';
  operator: '>';
  threshold: number;
  channel: 'email' | 'webhook';
  enabled: boolean;
}

export interface OverviewMetrics {
  traceCount: number;
  spanCount: number;
  totalTokens: number;
  totalCost: number;
  errorRate: number;
  p95LatencyMs: number;
  trend: Array<{ time: string; traces: number; errors: number; cost: number }>;
  modelUsage: Array<{ model: string; calls: number; tokens: number; cost: number }>;
}

export interface AttributionEvidence {
  spanId: string;
  signal: 'error' | 'latency' | 'tool' | 'handoff' | 'semantic';
  observation: string;
  score: number | null;
}

export interface FailureAttribution {
  traceId: string;
  method: string;
  methodVersion: string;
  rootSpanId: string | null;
  score: number | null;
  propagationPath: string[];
  evidence: AttributionEvidence[];
  status: 'demo_heuristic' | 'no_failure';
}

export interface GroundTruthLabel {
  traceId: string;
  rootSpanId: string;
  failureType: 'tool_failure' | 'llm_failure' | 'handoff_failure' | 'workflow_failure' | 'other';
  note: string;
  createdAt: string;
}
