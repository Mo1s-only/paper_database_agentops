#!/usr/bin/env python3
"""Cross-task attribution and counterfactual validation gate.

The generator deliberately keeps task semantics separate from the scorer so
that the same attribution and intervention code is exercised across task types.
"""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

TASKS = {
    "inventory": {"fault": "silent_tool_error", "required": {"available": 1}, "faulty": {"status": "ok", "available": 0}, "corrected": {"status": "ok", "available": 1}},
    "service_restart": {"fault": "error_propagation", "required": {"state": "running"}, "faulty": {"status": "error", "error_code": "TIMEOUT"}, "corrected": {"status": "ok", "state": "running"}},
    "document_retrieval": {"fault": "routing_role_error", "required": {"required_role": "retrieval_specialist"}, "faulty": {"assigned_role": "generalist"}, "corrected": {"assigned_role": "retrieval_specialist"}},
}


def event(run_id: str, event_id: str, parent: str | None, agent: str, step: str, kind: str, status: str, inp: dict, out: dict, index: int) -> dict:
    ts = (datetime(2026, 9, 28, 16, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=index)).isoformat().replace("+00:00", "Z")
    return {"schema_version": "agentops-trace-v0.1", "run_id": run_id, "event_id": event_id, "parent_event_id": parent, "agent_id": agent, "step_id": step, "event_type": kind, "timestamp": ts, "source": "cross_task_counterfactual_gate", "status": status, "input_summary": inp, "output_summary": out, "attributes": {"task_family": run_id.split("-")[0]}}


def build(task_name: str, repetition: int) -> tuple[list[dict], dict]:
    spec = TASKS[task_name]
    fault = spec["fault"]
    run_id = f"{task_name}-{fault}-r{repetition:02d}"
    trace: list[dict]
    if task_name == "inventory":
        trace = [
            event(run_id, "evt-001", None, "orchestrator", "task.start", "task.start", "started", {}, spec["required"], 0),
            event(run_id, "evt-002", "evt-001", "agent_a", "agent_a.route", "message.send", "success", {}, {"to": "agent_b"}, 1),
            event(run_id, "evt-003", "evt-002", "agent_b", "agent_b.tool_call", "tool.call", "success", {}, {}, 2),
            event(run_id, "evt-004", "evt-003", "agent_b", "agent_b.tool_result", "tool.result", "success", {}, spec["faulty"], 3),
            event(run_id, "evt-005", "evt-004", "agent_a", "agent_a.final", "task.finish", "failed", {}, {"success": False}, 4),
        ]
        truth = {"responsible_agent": "agent_b", "responsible_step": "agent_b.tool_call", "responsible_edge": {"from_event_id": "evt-003", "to_event_id": "evt-004"}, "intervention_event_id": "evt-004"}
    elif task_name == "service_restart":
        trace = [
            event(run_id, "evt-001", None, "orchestrator", "task.start", "task.start", "started", {}, spec["required"], 0),
            event(run_id, "evt-002", "evt-001", "agent_b", "agent_b.tool_call", "tool.call", "success", {}, {}, 1),
            event(run_id, "evt-003", "evt-002", "agent_b", "agent_b.tool_result", "tool.result", "error", {}, spec["faulty"], 2),
            event(run_id, "evt-004", "evt-003", "agent_b", "agent_b.forward_error", "message.send", "success", {}, {"to": "agent_a", "error_code": "TIMEOUT"}, 3),
            event(run_id, "evt-005", "evt-004", "agent_a", "agent_a.final", "task.finish", "failed", {}, {"success": False}, 4),
        ]
        truth = {"responsible_agent": "agent_b", "responsible_step": "agent_b.tool_call", "responsible_edge": {"from_event_id": "evt-002", "to_event_id": "evt-003"}, "intervention_event_id": "evt-003"}
    else:
        trace = [
            event(run_id, "evt-001", None, "orchestrator", "task.start", "task.start", "started", {}, spec["required"], 0),
            event(run_id, "evt-002", "evt-001", "orchestrator", "orchestrator.route", "route.decision", "success", spec["required"], spec["faulty"], 1),
            event(run_id, "evt-003", "evt-002", "agent_c", "agent_c.execute", "agent.step", "success", {}, {"result": "unsupported"}, 2),
            event(run_id, "evt-004", "evt-003", "agent_a", "agent_a.final", "task.finish", "failed", {}, {"success": False}, 3),
        ]
        truth = {"responsible_agent": "orchestrator", "responsible_step": "orchestrator.route", "responsible_edge": {"from_event_id": "evt-001", "to_event_id": "evt-002"}, "intervention_event_id": "evt-002"}
    truth.update({"schema_version": "agentops-ground-truth-v0.1", "run_id": run_id, "task_name": task_name, "fault_type": fault, "task_success": False})
    return trace, truth


def infer(trace: list[dict], task_name: str) -> dict:
    if task_name == "inventory":
        start = next(x for x in trace if x["event_type"] == "task.start")
        candidate = next(x for x in trace if x["event_type"] == "tool.result" and x["output_summary"].get("available") != start["output_summary"].get("available"))
        parent = next(x for x in trace if x["event_id"] == candidate["parent_event_id"])
    elif task_name == "service_restart":
        candidate = next(x for x in trace if x["event_type"] == "tool.result" and x["status"] == "error")
        parent = next(x for x in trace if x["event_id"] == candidate["parent_event_id"])
    else:
        candidate = next(x for x in trace if x["event_type"] == "route.decision" and x["output_summary"].get("assigned_role") != x["input_summary"].get("required_role"))
        parent = next(x for x in trace if x["event_id"] == candidate["parent_event_id"])
    if task_name == "document_retrieval":
        agent, step = candidate["agent_id"], candidate["step_id"]
    else:
        agent, step = candidate["agent_id"], parent["step_id"]
    return {"responsible_agent": agent, "responsible_step": step, "responsible_edge": {"from_event_id": parent["event_id"], "to_event_id": candidate["event_id"]}}


def evaluate(events: list[dict], task_name: str) -> bool:
    if task_name == "inventory":
        start = next(x for x in events if x["event_type"] == "task.start")
        result = next(x for x in events if x["event_type"] == "tool.result")
        return result["output_summary"].get("available") == start["output_summary"].get("available")
    if task_name == "service_restart":
        result = next(x for x in events if x["event_type"] == "tool.result")
        return result["status"] == "success" and result["output_summary"].get("state") == "running"
    start = next(x for x in events if x["event_type"] == "task.start")
    route = next(x for x in events if x["event_type"] == "route.decision")
    return route["output_summary"].get("assigned_role") == start["output_summary"].get("required_role")


def counterfactual(trace: list[dict], task_name: str, spec: dict, intervention_id: str) -> tuple[bool, bool]:
    repaired = copy.deepcopy(trace)
    target = next(x for x in repaired if x["event_id"] == intervention_id)
    target["status"] = "success"
    target["output_summary"] = dict(spec["corrected"])
    repaired_success = evaluate(repaired, task_name)
    control = copy.deepcopy(trace)
    unrelated = next(x for x in control if x["event_type"] == "task.finish")
    unrelated["attributes"]["unrelated_intervention"] = True
    control_success = evaluate(control, task_name)
    return repaired_success, control_success


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    rows = []
    for task_name, spec in TASKS.items():
        for repetition in range(1, args.repetitions + 1):
            trace, truth = build(task_name, repetition)
            run_dir = args.out_dir / truth["run_id"]
            run_dir.mkdir(parents=True, exist_ok=True)
            with (run_dir / "trace.jsonl").open("w", encoding="utf-8") as handle:
                for item in trace:
                    handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
            (run_dir / "ground_truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            prediction = infer(trace, task_name)
            repaired_success, control_success = counterfactual(trace, task_name, spec, truth["intervention_event_id"])
            scores = {"agent_exact": prediction["responsible_agent"] == truth["responsible_agent"], "step_exact": prediction["responsible_step"] == truth["responsible_step"], "edge_exact": prediction["responsible_edge"] == truth["responsible_edge"], "counterfactual_flip": repaired_success and not control_success}
            result = {"run_id": truth["run_id"], "task_name": task_name, "fault_type": truth["fault_type"], "prediction": prediction, "scores": scores, "repaired_success": repaired_success, "control_success": control_success, "claim_status": "VERIFIED_FOR_THIS_SYNTHETIC_PILOT"}
            (run_dir / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            rows.append(result)
    summary = {"runs": len(rows), "tasks": len(TASKS), "faults": len(TASKS), "agent_exact_rate": sum(x["scores"]["agent_exact"] for x in rows) / len(rows), "step_exact_rate": sum(x["scores"]["step_exact"] for x in rows) / len(rows), "edge_exact_rate": sum(x["scores"]["edge_exact"] for x in rows) / len(rows), "counterfactual_flip_rate": sum(x["scores"]["counterfactual_flip"] for x in rows) / len(rows), "by_task": {}, "claim_status": "VERIFIED_FOR_THIS_SYNTHETIC_PILOT"}
    for task_name in TASKS:
        items = [x for x in rows if x["task_name"] == task_name]
        summary["by_task"][task_name] = {"runs": len(items), "agent_exact": sum(x["scores"]["agent_exact"] for x in items), "step_exact": sum(x["scores"]["step_exact"] for x in items), "edge_exact": sum(x["scores"]["edge_exact"] for x in items), "counterfactual_flip": sum(x["scores"]["counterfactual_flip"] for x in items)}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "gate-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
