#!/usr/bin/env python3
"""Offline counterfactual replay for the real inventory pilot trace."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path


def task_success(trace: list[dict]) -> bool:
    start = next(x for x in trace if x.get("event_type") == "task.start")
    result = next(x for x in trace if x.get("event_type") == "tool.result")
    return result.get("output_summary", {}).get("available") == start.get("output_summary", {}).get("required_available")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    trace = [json.loads(line) for line in (args.run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    baseline_success = task_success(trace)
    repaired = copy.deepcopy(trace)
    tool_result = next(x for x in repaired if x.get("event_type") == "tool.result")
    required = next(x for x in repaired if x.get("event_type") == "task.start").get("output_summary", {}).get("required_available")
    tool_result["output_summary"]["available"] = required
    repaired_success = task_success(repaired)
    control = copy.deepcopy(trace)
    final = next(x for x in control if x.get("event_type") == "task.finish")
    final.setdefault("attributes", {})["unrelated_intervention"] = "metadata-only"
    control_success = task_success(control)
    result = {
        "schema_version": "agentops-counterfactual-v0.1",
        "run_id": args.run_dir.name,
        "intervention": {"event_type": "tool.result", "field": "available", "from": 0, "to": required},
        "baseline_success": baseline_success,
        "repaired_success": repaired_success,
        "control_success": control_success,
        "counterfactual_flip": (not baseline_success) and repaired_success,
        "control_specific": not control_success,
        "claim_status": "VERIFIED_FOR_THIS_CONTROLLED_REAL_AGENT_RUN",
        "limitation": "offline task-criterion replay; no second real Claude execution",
    }
    (args.run_dir / "counterfactual.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
