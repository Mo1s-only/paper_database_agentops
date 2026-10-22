#!/usr/bin/env python3
"""Create sanitized task-contract fixtures and hidden repair/control plans."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PILOT_DIR = Path(__file__).resolve().parents[1] / "failure_pilot"
sys.path.insert(0, str(PILOT_DIR))
from run_fault_matrix import make_event  # noqa: E402

TASKS = {
    "inventory": {"expected": {"available": 1}, "faulty": {"status": "ok", "available": 0}, "fixed": {"status": "ok", "available": 1}},
    "service": {"expected": {"state": "running"}, "faulty": {"status": "error", "error_code": "TIMEOUT"}, "fixed": {"status": "ok", "state": "running"}},
    "routing": {"expected": {"required_role": "retrieval_specialist"}, "faulty": {"assigned_role": "generalist"}, "fixed": {"assigned_role": "retrieval_specialist"}},
}


def build(task: str, repetition: int) -> tuple[list[dict], dict, dict]:
    run_id = f"fixture-{task}-{repetition}"
    if task == "inventory":
        trace = [
            make_event(run_id, "evt-001", None, "orchestrator", "task.start", "task.start", "started", {}, {"available": 1}, 0),
            make_event(run_id, "evt-002", "evt-001", "agent_a", "agent_a.route", "message.send", "success", {}, {"to": "agent_b"}, 1),
            make_event(run_id, "evt-003", "evt-002", "agent_b", "agent_b.tool_call", "tool.call", "success", {}, {}, 2),
            make_event(run_id, "evt-004", "evt-003", "agent_b", "agent_b.tool_result", "tool.result", "success", {}, TASKS[task]["faulty"], 3),
            make_event(run_id, "evt-005", "evt-004", "agent_a", "agent_a.final", "task.finish", "failed", {}, {"success": False}, 4),
        ]
        truth = {"responsible_agent": "agent_b", "responsible_step": "agent_b.tool_call", "responsible_edge": {"from_event_id": "evt-003", "to_event_id": "evt-004"}, "responsible_action_event_id": "evt-003"}
        target_id = "evt-004"
    elif task == "service":
        trace = [
            make_event(run_id, "evt-001", None, "orchestrator", "task.start", "task.start", "started", {}, {"state": "running"}, 0),
            make_event(run_id, "evt-002", "evt-001", "agent_b", "agent_b.tool_call", "tool.call", "success", {}, {}, 1),
            make_event(run_id, "evt-003", "evt-002", "agent_b", "agent_b.tool_result", "tool.result", "error", {}, TASKS[task]["faulty"], 2),
            make_event(run_id, "evt-004", "evt-003", "agent_b", "agent_b.forward_error", "message.send", "success", {}, {"to": "agent_a"}, 3),
            make_event(run_id, "evt-005", "evt-004", "agent_a", "agent_a.final", "task.finish", "failed", {}, {"success": False}, 4),
        ]
        truth = {"responsible_agent": "agent_b", "responsible_step": "agent_b.tool_call", "responsible_edge": {"from_event_id": "evt-002", "to_event_id": "evt-003"}, "responsible_action_event_id": "evt-002"}
        target_id = "evt-003"
    else:
        expected_role = TASKS[task]["expected"]["required_role"]
        trace = [
            make_event(run_id, "evt-001", None, "orchestrator", "task.start", "task.start", "started", {}, {"required_role": expected_role}, 0),
            make_event(run_id, "evt-002", "evt-001", "orchestrator", "orchestrator.route", "route.decision", "success", {"required_role": expected_role}, TASKS[task]["faulty"], 1),
            make_event(run_id, "evt-003", "evt-002", "agent_c", "agent_c.execute", "agent.step", "success", {}, {"result": "unsupported"}, 2),
            make_event(run_id, "evt-004", "evt-003", "agent_a", "agent_a.final", "task.finish", "failed", {}, {"success": False}, 3),
        ]
        truth = {"responsible_agent": "orchestrator", "responsible_step": "orchestrator.route", "responsible_edge": {"from_event_id": "evt-001", "to_event_id": "evt-002"}, "responsible_action_event_id": "evt-002"}
        target_id = "evt-002"
    truth.update({"run_id": run_id, "task_name": task, "fault_type": {"inventory": "silent_tool_error", "service": "error_propagation", "routing": "routing_role_error"}[task]})
    plan = {
        "run_id": run_id,
        "repair": {"event_id": target_id, "status": "success", "output_summary": TASKS[task]["fixed"]},
        "control": {"event_id": trace[-1]["event_id"], "operation": "mark_unrelated_final_event"},
    }
    return trace, truth, plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")
    args.out_dir.mkdir(parents=True, exist_ok=False)
    index = 0
    for task in TASKS:
        for repetition in range(1, args.repetitions + 1):
            index += 1
            opaque_id = f"cf-blind-{index:04d}"
            trace, truth, plan = build(task, repetition)
            run_dir = args.out_dir / opaque_id
            run_dir.mkdir()
            for event in trace:
                event["run_id"] = opaque_id
                event.pop("attributes", None)
                event["source"] = "sanitized_synthetic_fixture"
            truth["run_id"] = opaque_id
            plan["run_id"] = opaque_id
            for name, payload in (("trace.jsonl", None), ("ground_truth.json", truth), ("repair_plan.json", plan)):
                path = run_dir / name
                with path.open("x", encoding="utf-8", newline="\n") as handle:
                    if name == "trace.jsonl":
                        for event in trace:
                            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
                    else:
                        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                        handle.write("\n")
    print(f"Prepared {index} sanitized counterfactual fixtures at {args.out_dir}; labels remain in truth only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
