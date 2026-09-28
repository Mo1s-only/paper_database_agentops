#!/usr/bin/env python3
"""Generate and score a small deterministic fault matrix for the next gate."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

FAULTS = ("silent_tool_error", "error_propagation", "routing_role_error")


def make_event(run_id: str, event_id: str, parent: str | None, agent: str, step: str,
               event_type: str, status: str, inp: dict, out: dict, index: int) -> dict:
    stamp = (datetime(2026, 9, 28, 15, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=index)).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": "agentops-trace-v0.1",
        "run_id": run_id,
        "event_id": event_id,
        "parent_event_id": parent,
        "agent_id": agent,
        "step_id": step,
        "event_type": event_type,
        "timestamp": stamp,
        "source": "deterministic_fault_matrix",
        "status": status,
        "input_summary": inp,
        "output_summary": out,
        "attributes": {"fault_matrix": True},
    }


def build_run(fault: str, repetition: int) -> tuple[list[dict], dict]:
    run_id = f"{fault}-r{repetition:02d}"
    if fault == "silent_tool_error":
        trace = [
            make_event(run_id, "evt-001", None, "orchestrator", "task.start", "task.start", "started", {}, {"item": "alpha", "required_available": 1}, 0),
            make_event(run_id, "evt-002", "evt-001", "agent_a", "agent_a.route", "message.send", "success", {}, {"to": "agent_b", "item": "alpha"}, 1),
            make_event(run_id, "evt-003", "evt-002", "agent_b", "agent_b.tool_call", "tool.call", "success", {"item": "alpha"}, {}, 2),
            make_event(run_id, "evt-004", "evt-003", "agent_b", "agent_b.tool_result", "tool.result", "success", {"item": "alpha"}, {"status": "ok", "available": 0}, 3),
            make_event(run_id, "evt-005", "evt-004", "agent_a", "agent_a.final", "task.finish", "failed", {"required_available": 1, "observed_available": 0}, {"success": False}, 4),
        ]
        truth = {"responsible_agent": "agent_b", "responsible_step": "agent_b.tool_call", "responsible_edge": {"from_event_id": "evt-003", "to_event_id": "evt-004"}}
    elif fault == "error_propagation":
        trace = [
            make_event(run_id, "evt-001", None, "orchestrator", "task.start", "task.start", "started", {}, {"required": "answer"}, 0),
            make_event(run_id, "evt-002", "evt-001", "agent_b", "agent_b.tool_call", "tool.call", "success", {"tool": "retrieval"}, {}, 1),
            make_event(run_id, "evt-003", "evt-002", "agent_b", "agent_b.tool_result", "tool.result", "error", {"tool": "retrieval"}, {"error_code": "TIMEOUT"}, 2),
            make_event(run_id, "evt-004", "evt-003", "agent_b", "agent_b.forward_error", "message.send", "success", {"error_code": "TIMEOUT"}, {"to": "agent_a", "message": "no answer"}, 3),
            make_event(run_id, "evt-005", "evt-004", "agent_a", "agent_a.final", "task.finish", "failed", {"received": "no answer"}, {"success": False}, 4),
        ]
        truth = {"responsible_agent": "agent_b", "responsible_step": "agent_b.tool_call", "responsible_edge": {"from_event_id": "evt-002", "to_event_id": "evt-003"}}
    elif fault == "routing_role_error":
        trace = [
            make_event(run_id, "evt-001", None, "orchestrator", "task.start", "task.start", "started", {}, {"required_role": "inventory_specialist"}, 0),
            make_event(run_id, "evt-002", "evt-001", "orchestrator", "orchestrator.route", "route.decision", "success", {"required_role": "inventory_specialist"}, {"assigned_role": "generalist", "assigned_agent": "agent_c"}, 1),
            make_event(run_id, "evt-003", "evt-002", "agent_c", "agent_c.execute", "agent.step", "success", {"role": "generalist"}, {"decision": "unsupported"}, 2),
            make_event(run_id, "evt-004", "evt-003", "agent_a", "agent_a.final", "task.finish", "failed", {"decision": "unsupported"}, {"success": False}, 3),
        ]
        truth = {"responsible_agent": "orchestrator", "responsible_step": "orchestrator.route", "responsible_edge": {"from_event_id": "evt-001", "to_event_id": "evt-002"}}
    else:
        raise ValueError(f"unknown fault: {fault}")
    truth.update({"schema_version": "agentops-ground-truth-v0.1", "run_id": run_id, "fault_type": fault, "task_success": False})
    truth["evidence_event_ids"] = [truth["responsible_edge"]["from_event_id"], truth["responsible_edge"]["to_event_id"]]
    return trace, truth


def infer(trace: list[dict], fault: str) -> dict:
    candidate = None
    if fault == "silent_tool_error":
        start = next(x for x in trace if x["event_type"] == "task.start")
        required = start["output_summary"].get("required_available")
        candidate = next((x for x in trace if x["event_type"] == "tool.result" and x["status"] == "success" and x["output_summary"].get("available") != required), None)
    elif fault == "error_propagation":
        candidate = next((x for x in trace if x["event_type"] == "tool.result" and x["status"] == "error"), None)
    elif fault == "routing_role_error":
        candidate = next((x for x in trace if x["event_type"] == "route.decision" and x["output_summary"].get("assigned_role") != x["input_summary"].get("required_role")), None)
    if candidate is None:
        return {"prediction_status": "ambiguous"}
    parent = next((x for x in trace if x["event_id"] == candidate.get("parent_event_id")), {})
    if fault == "routing_role_error":
        agent, step = candidate["agent_id"], candidate["step_id"]
    else:
        agent, step = candidate["agent_id"], parent.get("step_id")
    return {"prediction_status": "single_candidate", "responsible_agent": agent, "responsible_step": step, "responsible_edge": {"from_event_id": parent.get("event_id"), "to_event_id": candidate.get("event_id")}}


def score(prediction: dict, truth: dict) -> dict:
    return {
        "agent_exact_match": prediction.get("responsible_agent") == truth.get("responsible_agent"),
        "step_exact_match": prediction.get("responsible_step") == truth.get("responsible_step"),
        "edge_exact_match": prediction.get("responsible_edge") == truth.get("responsible_edge"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    summaries = []
    for fault in FAULTS:
        for repetition in range(1, args.repetitions + 1):
            run_dir = args.out_dir / f"{fault}-r{repetition:02d}"
            run_dir.mkdir(parents=True, exist_ok=True)
            trace, truth = build_run(fault, repetition)
            with (run_dir / "trace.jsonl").open("w", encoding="utf-8") as handle:
                for item in trace:
                    handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
            (run_dir / "ground_truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            prediction = infer(trace, fault)
            scores = score(prediction, truth)
            result = {"run_id": truth["run_id"], "fault_type": fault, "prediction": prediction, "scores": scores, "claim_status": "VERIFIED_FOR_THIS_SYNTHETIC_PILOT"}
            (run_dir / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            summaries.append(result)
    aggregate = {"runs": len(summaries), "by_fault": {}, "all_agent_exact": all(x["scores"]["agent_exact_match"] for x in summaries), "all_step_exact": all(x["scores"]["step_exact_match"] for x in summaries), "all_edge_exact": all(x["scores"]["edge_exact_match"] for x in summaries), "claim_status": "VERIFIED_FOR_THIS_SYNTHETIC_PILOT"}
    for fault in FAULTS:
        items = [x for x in summaries if x["fault_type"] == fault]
        aggregate["by_fault"][fault] = {"runs": len(items), "agent_exact": sum(x["scores"]["agent_exact_match"] for x in items), "step_exact": sum(x["scores"]["step_exact_match"] for x in items), "edge_exact": sum(x["scores"]["edge_exact_match"] for x in items)}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "matrix-summary.json").write_text(json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(aggregate, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
