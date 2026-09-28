#!/usr/bin/env python3
"""Generate a deterministic two-agent failure trace with an independent truth file."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def event(run_id: str, event_id: str, parent_event_id: str | None, agent_id: str,
          step_id: str, event_type: str, source: str, status: str,
          input_summary: dict, output_summary: dict, timestamp: str,
          attributes: dict | None = None) -> dict:
    return {
        "schema_version": "agentops-trace-v0.1",
        "run_id": run_id,
        "event_id": event_id,
        "parent_event_id": parent_event_id,
        "agent_id": agent_id,
        "step_id": step_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "source": source,
        "status": status,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "attributes": attributes or {},
    }


def build_trace(run_id: str) -> tuple[list[dict], dict]:
    # One-second spacing keeps ordering deterministic while preserving an ISO time field.
    base = datetime(2026, 9, 28, 12, 0, 0, tzinfo=timezone.utc)
    stamps = [(base.replace(second=i)).isoformat().replace("+00:00", "Z") for i in range(8)]
    trace = [
        event(run_id, "evt-001", None, "orchestrator", "task.start", "task.start", "workflow", "started",
              {"task": "check_alpha_inventory"}, {"required_available": 1, "item": "alpha"}, stamps[0]),
        event(run_id, "evt-002", "evt-001", "agent_a", "agent_a.plan", "agent.step", "agent_log", "success",
              {"task": "check_alpha_inventory"}, {"plan": "ask_agent_b_to_query_inventory"}, stamps[1]),
        event(run_id, "evt-003", "evt-002", "agent_a", "agent_a.route", "message.send", "message_bus", "success",
              {"to": "agent_b"}, {"query": "alpha", "required_available": 1}, stamps[2]),
        event(run_id, "evt-004", "evt-003", "agent_b", "agent_b.tool_call", "tool.call", "tool_runtime", "started",
              {"tool": "inventory_lookup", "item": "alpha"}, {}, stamps[3]),
        event(run_id, "evt-005", "evt-004", "agent_b", "agent_b.tool_result", "tool.result", "fake_inventory", "success",
              {"tool": "inventory_lookup", "item": "alpha"}, {"status": "ok", "available": 0}, stamps[4]),
        event(run_id, "evt-006", "evt-005", "agent_b", "agent_b.decide", "agent.step", "agent_log", "success",
              {"available": 0, "required_available": 1}, {"decision": "unavailable"}, stamps[5]),
        event(run_id, "evt-007", "evt-006", "agent_b", "agent_b.report", "message.send", "message_bus", "success",
              {"to": "agent_a"}, {"item": "alpha", "available": 0}, stamps[6]),
        event(run_id, "evt-008", "evt-007", "agent_a", "agent_a.final", "task.finish", "workflow", "failed",
              {"item": "alpha", "required_available": 1, "reported_available": 0}, {"success": False}, stamps[7]),
    ]
    # This is intentionally separate from the observed trace. It describes the injected fault,
    # but no trace event contains a corresponding "fault_injected" flag.
    truth = {
        "schema_version": "agentops-ground-truth-v0.1",
        "run_id": run_id,
        "task_success": False,
        "fault_type": "silent_tool_error",
        "responsible_agent": "agent_b",
        "responsible_step": "agent_b.tool_call",
        "responsible_edge": {"from_event_id": "evt-004", "to_event_id": "evt-005"},
        "evidence_event_ids": ["evt-004", "evt-005", "evt-006", "evt-008"],
        "expected_tool_output": {"available": 1},
        "observed_tool_output": {"available": 0},
    }
    return trace, truth


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    run_id = args.run_id or "failure-pilot-20260928-120000Z"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    trace, truth = build_trace(run_id)
    with (args.out_dir / "trace.jsonl").open("w", encoding="utf-8") as handle:
        for item in trace:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    (args.out_dir / "ground_truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out_dir / "run-meta.json").write_text(json.dumps({"run_id": run_id, "generated_at": utc_now(), "deterministic": True}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": run_id, "trace_events": len(trace), "ground_truth": str(args.out_dir / "ground_truth.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
