#!/usr/bin/env python3
"""Prepare a zero-network manifest for the next real AgentSight pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


CASES = [
    {
        "case_id": "inventory-silent-tool",
        "task_family": "inventory",
        "fault_type": "silent_tool_error",
        "agents": ["agent_a", "agent_b"],
        "planned_api_calls": 2,
        "responsible_agent": "agent_b",
        "responsible_step": "agent_b.bash_tool_call",
        "responsible_edge": {"from": "agent_b.bash_tool_call", "to": "agent_b.tool_result"},
        "expected": {"item": "alpha", "available": 1},
        "observed_fault": {"status": "ok", "available": 0},
        "artifacts": ["route.json", "decision.json", "session.db", "raw-stream.log", "trace.jsonl", "ground_truth.json", "analysis.json", "cost.json"],
    },
    {
        "case_id": "service-error-propagation",
        "task_family": "service_restart",
        "fault_type": "error_propagation",
        "agents": ["agent_a", "agent_b"],
        "planned_api_calls": 2,
        "responsible_agent": "agent_b",
        "responsible_step": "agent_b.bash_tool_call",
        "responsible_edge": {"from": "agent_b.bash_tool_call", "to": "agent_b.tool_result"},
        "expected": {"service": "api", "state": "running"},
        "observed_fault": {"status": "error", "error_code": "TIMEOUT"},
        "artifacts": ["service-task.json", "service-decision.json", "session.db", "raw-stream.log", "trace.jsonl", "ground_truth.json", "analysis.json", "cost.json"],
    },
    {
        "case_id": "retrieval-routing-error",
        "task_family": "document_retrieval",
        "fault_type": "routing_role_error",
        "agents": ["orchestrator", "agent_c"],
        "planned_api_calls": 2,
        "responsible_agent": "orchestrator",
        "responsible_step": "orchestrator.route",
        "responsible_edge": {"from": "task.start", "to": "orchestrator.route"},
        "expected": {"required_role": "retrieval_specialist", "query": "alpha policy"},
        "observed_fault": {"assigned_role": "generalist", "assigned_agent": "agent_c"},
        "artifacts": ["route.json", "retrieval-decision.json", "session.db", "raw-stream.log", "trace.jsonl", "ground_truth.json", "analysis.json", "cost.json"],
    },
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--case", choices=[x["case_id"] for x in CASES], default=None, help="prepare one case only; omit to list the full catalog")
    parser.add_argument("--upper-bound-usd-per-call", type=float, default=0.13)
    parser.add_argument("--hard-stop-usd", type=float, default=1.0)
    args = parser.parse_args()
    selected = [x for x in CASES if args.case is None or x["case_id"] == args.case]
    total_calls = sum(int(x["planned_api_calls"]) for x in selected)
    manifest = {
        "schema_version": "agentops-real-pilot-plan-v0.1",
        "execution": "DRY_RUN_ONLY",
        "network_calls_made": 0,
        "planned_api_calls": total_calls,
        "upper_bound_usd_per_call": args.upper_bound_usd_per_call,
        "planned_cost_upper_bound_usd": round(total_calls * args.upper_bound_usd_per_call, 6),
        "hard_stop_usd": args.hard_stop_usd,
        "hard_stop_total_usd": args.hard_stop_usd,
        "selected_case": args.case,
        "cases": selected,
        "execution_rule": "Do not execute this manifest automatically; run one case only after budget approval and preflight.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"execution": manifest["execution"], "network_calls_made": 0, "planned_api_calls": total_calls, "planned_cost_upper_bound_usd": manifest["planned_cost_upper_bound_usd"], "hard_stop_usd": args.hard_stop_usd}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
