import type { AlertRule, Project, Span, Trace } from './types';

export const projects: Project[] = [
  { id: 'research-copilot', name: '论文研究 Copilot', environment: 'production', apiKeyHint: 'aop_••••7F2A', traces24h: 184 },
  { id: 'multi-agent-bench', name: 'Multi-Agent Benchmark', environment: 'staging', apiKeyHint: 'aop_••••91CD', traces24h: 96 },
  { id: 'local-sandbox', name: 'Local Sandbox', environment: 'development', apiKeyHint: 'aop_••••3B80', traces24h: 31 },
];

const base = new Date('2026-10-19T12:00:00+08:00').getTime();
const iso = (offsetMinutes: number) => new Date(base - offsetMinutes * 60_000).toISOString();

function span(
  id: string,
  parentId: string | null,
  name: string,
  kind: Span['kind'],
  agent: string,
  offset: number,
  durationMs: number,
  extras: Partial<Span> = {},
): Span {
  return {
    id, parentId, name, kind, agent, startedAt: iso(offset), durationMs,
    input: extras.input ?? 'Structured task payload',
    output: extras.output ?? 'Completed with a grounded response.',
    tokens: extras.tokens ?? 0,
    cost: extras.cost ?? 0,
    status: extras.status ?? 'ok',
    ...extras,
  };
}

export const traces: Trace[] = [
  {
    id: 'tr_9c27a81f0d6e', projectId: 'research-copilot', name: 'literature_review_pipeline',
    startedAt: iso(8), durationMs: 18_420, status: 'ok', tokens: 16_842, cost: 0.0824,
    tags: ['production', 'literature'],
    spans: [
      span('sp_a1', null, 'Literature review workflow', 'workflow', 'orchestrator', 8, 18_420),
      span('sp_a2', 'sp_a1', 'Plan research question', 'agent', 'planner', 8, 1_820),
      span('sp_a3', 'sp_a2', 'gpt-4.1 reasoning', 'llm', 'planner', 8, 1_360, { model: 'gpt-4.1', tokens: 2_840, cost: 0.0184 }),
      span('sp_a4', 'sp_a1', 'Search local corpus', 'tool', 'researcher', 6, 620),
      span('sp_a5', 'sp_a1', 'Synthesize evidence', 'agent', 'researcher', 5, 7_480),
      span('sp_a6', 'sp_a5', 'claude-3.7-sonnet synthesis', 'llm', 'researcher', 5, 6_940, { model: 'claude-3.7-sonnet', tokens: 8_236, cost: 0.0412 }),
      span('sp_a7', 'sp_a1', 'Reviewer pass', 'agent', 'reviewer', 2, 5_210),
      span('sp_a8', 'sp_a7', 'gpt-4.1 critique', 'llm', 'reviewer', 2, 4_710, { model: 'gpt-4.1', tokens: 5_766, cost: 0.0228 }),
    ],
  },
  {
    id: 'tr_819ca7752bb1', projectId: 'multi-agent-bench', name: 'incident_root_cause_analysis',
    startedAt: iso(46), durationMs: 42_180, status: 'error', tokens: 11_406, cost: 0.0618,
    tags: ['staging', 'rca', 'retry'],
    spans: [
      span('sp_b1', null, 'RCA workflow', 'workflow', 'orchestrator', 46, 42_180, { status: 'error', error: 'Tool timeout propagated to final answer.' }),
      span('sp_b2', 'sp_b1', 'Collect telemetry', 'agent', 'collector', 46, 8_420),
      span('sp_b3', 'sp_b2', 'Query ClickHouse', 'tool', 'collector', 45, 7_860),
      span('sp_b4', 'sp_b1', 'Correlate failure signals', 'agent', 'analyst', 38, 19_440),
      span('sp_b5', 'sp_b4', 'gpt-4.1 analysis', 'llm', 'analyst', 38, 8_020, { model: 'gpt-4.1', tokens: 6_392, cost: 0.0362 }),
      span('sp_b6', 'sp_b4', 'Fetch service graph', 'tool', 'analyst', 30, 10_000, { status: 'error', error: 'Timeout after 10s' }),
      span('sp_b7', 'sp_b1', 'Generate explanation', 'llm', 'reviewer', 27, 11_340, { model: 'gpt-4.1-mini', tokens: 5_014, cost: 0.0256, status: 'error', error: 'Insufficient tool context' }),
    ],
  },
  {
    id: 'tr_d48f70312ab0', projectId: 'research-copilot', name: 'citation_consistency_check',
    startedAt: iso(92), durationMs: 7_860, status: 'ok', tokens: 6_780, cost: 0.0241,
    tags: ['production', 'quality-gate'],
    spans: [
      span('sp_c1', null, 'Citation audit', 'workflow', 'orchestrator', 92, 7_860),
      span('sp_c2', 'sp_c1', 'Extract claims', 'tool', 'auditor', 92, 980),
      span('sp_c3', 'sp_c1', 'Verify evidence links', 'agent', 'auditor', 90, 5_840),
      span('sp_c4', 'sp_c3', 'gpt-4.1-mini verification', 'llm', 'auditor', 90, 5_180, { model: 'gpt-4.1-mini', tokens: 6_780, cost: 0.0241 }),
    ],
  },
  {
    id: 'tr_4de71bb83a21', projectId: 'local-sandbox', name: 'tool_selection_probe',
    startedAt: iso(140), durationMs: 3_260, status: 'ok', tokens: 2_126, cost: 0.0067,
    tags: ['development', 'probe'],
    spans: [
      span('sp_d1', null, 'Tool routing probe', 'workflow', 'router', 140, 3_260),
      span('sp_d2', 'sp_d1', 'Select tool', 'llm', 'router', 140, 1_680, { model: 'gpt-4.1-mini', tokens: 2_126, cost: 0.0067 }),
      span('sp_d3', 'sp_d1', 'Read fixture', 'tool', 'router', 138, 340),
    ],
  },
  {
    id: 'tr_f937a5c22042', projectId: 'multi-agent-bench', name: 'handoff_consistency_eval',
    startedAt: iso(205), durationMs: 28_640, status: 'running', tokens: 9_312, cost: 0.0438,
    tags: ['staging', 'handoff'],
    spans: [
      span('sp_e1', null, 'Handoff evaluation', 'workflow', 'orchestrator', 205, 28_640, { status: 'running' }),
      span('sp_e2', 'sp_e1', 'Coordinator turn', 'agent', 'coordinator', 205, 8_420),
      span('sp_e3', 'sp_e2', 'gpt-4.1 coordination', 'llm', 'coordinator', 205, 7_880, { model: 'gpt-4.1', tokens: 5_120, cost: 0.0302 }),
      span('sp_e4', 'sp_e1', 'Worker handoff', 'agent', 'worker-2', 197, 19_200, { status: 'running' }),
      span('sp_e5', 'sp_e4', 'gpt-4.1-mini execution', 'llm', 'worker-2', 197, 18_610, { model: 'gpt-4.1-mini', tokens: 4_192, cost: 0.0136, status: 'running' }),
    ],
  },
  {
    id: 'tr_11ad9e0c86f4', projectId: 'research-copilot', name: 'chapter_outline_generation',
    startedAt: iso(310), durationMs: 12_940, status: 'ok', tokens: 12_218, cost: 0.0572,
    tags: ['production', 'writing'],
    spans: [
      span('sp_f1', null, 'Outline generation', 'workflow', 'orchestrator', 310, 12_940),
      span('sp_f2', 'sp_f1', 'Retrieve thesis notes', 'tool', 'writer', 310, 840),
      span('sp_f3', 'sp_f1', 'Compose outline', 'llm', 'writer', 308, 9_720, { model: 'claude-3.7-sonnet', tokens: 9_404, cost: 0.0468 }),
      span('sp_f4', 'sp_f1', 'Validate structure', 'llm', 'reviewer', 298, 2_180, { model: 'gpt-4.1-mini', tokens: 2_814, cost: 0.0104 }),
    ],
  },
];

export const alertRules: AlertRule[] = [
  { id: 'al_1', name: '错误率突增', metric: 'error_rate', operator: '>', threshold: 8, channel: 'email', enabled: true },
  { id: 'al_2', name: 'P95 延迟过高', metric: 'latency_p95', operator: '>', threshold: 30_000, channel: 'webhook', enabled: true },
  { id: 'al_3', name: '每日成本预算', metric: 'daily_cost', operator: '>', threshold: 20, channel: 'email', enabled: false },
];
