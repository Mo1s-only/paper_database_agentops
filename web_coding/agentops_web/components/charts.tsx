'use client';

import type { OverviewMetrics } from '@/lib/types';
import { formatCompact, formatCost } from '@/lib/format';

export function TrendChart({ data }: { data: OverviewMetrics['trend'] }) {
  const width = 760;
  const height = 230;
  const pad = 24;
  const max = Math.max(...data.map((item) => item.traces), 1);
  const points = data.map((item, index) => {
    const x = pad + (index * (width - pad * 2)) / Math.max(data.length - 1, 1);
    const y = height - pad - (item.traces / max) * (height - pad * 2);
    return { x, y, ...item };
  });
  const line = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');
  const area = points.length ? `${line} L ${points.at(-1)!.x} ${height - pad} L ${points[0].x} ${height - pad} Z` : '';

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Trace 数量趋势">
        <defs>
          <linearGradient id="trace-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="var(--accent)" stopOpacity=".34" /><stop offset="1" stopColor="var(--accent)" stopOpacity="0" /></linearGradient>
        </defs>
        {[0, 1, 2, 3].map((row) => <line key={row} x1={pad} x2={width - pad} y1={pad + row * 56} y2={pad + row * 56} className="grid-line" />)}
        <path d={area} fill="url(#trace-area)" />
        <path d={line} className="trend-line" />
        {points.map((point) => <circle key={point.time} cx={point.x} cy={point.y} r="4" className="trend-dot"><title>{point.time}: {point.traces} traces</title></circle>)}
      </svg>
      <div className="chart-labels">{data.map((item) => <span key={item.time}>{item.time}</span>)}</div>
    </div>
  );
}

export function ModelUsage({ data }: { data: OverviewMetrics['modelUsage'] }) {
  const max = Math.max(...data.map((item) => item.tokens), 1);
  return (
    <div className="model-usage">
      {data.map((item, index) => (
        <div className="model-row" key={item.model}>
          <div className={`model-glyph model-${index + 1}`}>{item.model.slice(0, 1).toUpperCase()}</div>
          <div className="model-main">
            <div><strong>{item.model}</strong><span>{item.calls} calls</span></div>
            <div className="meter"><i style={{ width: `${(item.tokens / max) * 100}%` }} /></div>
          </div>
          <div className="model-value"><strong>{formatCompact(item.tokens)}</strong><span>{formatCost(item.cost)}</span></div>
        </div>
      ))}
    </div>
  );
}
