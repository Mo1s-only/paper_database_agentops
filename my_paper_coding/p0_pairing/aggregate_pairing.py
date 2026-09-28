#!/usr/bin/env python3
"""Aggregate marker-pairing pilot reports without overstating general recall."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    args = parser.parse_args()

    reports: list[dict[str, Any]] = []
    for path in sorted(args.root.glob("*/pairing-analysis.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        value["report_path"] = str(path.parent)
        reports.append(value)
    if not reports:
        raise SystemExit(f"no pairing-analysis.json found below {args.root}")

    pair_candidates = sum(int(r["marker_pair_candidates"]) for r in reports)
    pair_matches = sum(int(r["marker_pair_matches"]) for r in reports)
    latencies = [
        int(r["response_latency_ms"])
        for r in reports
        if r.get("response_latency_ms") is not None
    ]
    summary = {
        "schema_version": 1,
        "pilot_runs": len(reports),
        "agent_success_runs": sum(bool(r["agent_success"]) for r in reports),
        "gate_pass_runs": sum(bool(r["gate_pass"]) for r in reports),
        "marker_pair_candidates": pair_candidates,
        "marker_pair_matches": pair_matches,
        "marker_pair_precision": pair_matches / pair_candidates if pair_candidates else 0.0,
        "marker_pair_recall": pair_matches / len(reports),
        "response_latency_ms": {
            "n": len(latencies),
            "mean": mean(latencies) if latencies else None,
            "min": min(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "reports": reports,
        "interpretation": (
            "Controlled marker-pairing pilot only. These values do not estimate general "
            "request-response recall across unmarked or concurrent calls."
        ),
    }
    args.json_out.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    rows = [
        "# P0 请求—响应配对 Pilot 汇总",
        "",
        "> 本报告只统计带唯一 marker 的受控调用；不能替代并发、多请求和未标记调用的通用配对评测。",
        "",
        "| 项目 | 结果 |",
        "|---|---:|",
        f"| Pilot 运行数 | {summary['pilot_runs']} |",
        f"| Agent 成功数 | {summary['agent_success_runs']} |",
        f"| `gate_pass` 数 | {summary['gate_pass_runs']} |",
        f"| marker 配对候选数 | {pair_candidates} |",
        f"| marker 配对成功数 | {pair_matches} |",
        f"| marker 配对 Precision | {summary['marker_pair_precision']:.3f} |",
        f"| marker 配对 Recall | {summary['marker_pair_recall']:.3f} |",
        f"| 响应延迟均值（ms） | {summary['response_latency_ms']['mean']} |",
        f"| 响应延迟范围（ms） | {summary['response_latency_ms']['min']}–{summary['response_latency_ms']['max']} |",
        "",
        "## 证据边界",
        "",
        "- `VERIFIED`：本批次每条 marker 请求均找到包含同一 marker 的响应，且请求与响应共享观测 `pid/tid`。",
        "- `UNVERIFIED`：并发请求、未标记请求、请求重试和多轮工具调用的通用配对性能。",
        "- 下一闸门：将配对分析接入一个可重复的失败任务，并保留独立的责任 Agent/Step/Edge 真值。",
    ]
    args.markdown_out.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
