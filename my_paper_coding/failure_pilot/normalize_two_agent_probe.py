#!/usr/bin/env python3
"""Normalize the first two-agent AgentSight probe into the local trace schema."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def raw_processes(path: Path) -> tuple[list[int], list[int]]:
    agent_pids: list[int] = []
    tool_pids: list[int] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        data = item.get("data", {})
        command = str(data.get("full_command", ""))
        pid = data.get("pid")
        if not isinstance(pid, int):
            continue
        if "You are Agent A" in command or "You are Agent B" in command:
            agent_pids.append(pid)
        if "fake_inventory.py alpha" in command:
            tool_pids.append(pid)
    return sorted(set(agent_pids)), sorted(set(tool_pids))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    run_id = args.run_dir.name
    route = json.loads((args.run_dir / "workspace" / "route.json").read_text(encoding="utf-8"))
    decision = json.loads((args.run_dir / "workspace" / "decision.json").read_text(encoding="utf-8"))
    truth = json.loads((args.run_dir / "ground_truth.json").read_text(encoding="utf-8"))
    agent_pids, tool_pids = raw_processes(args.run_dir / "raw-stream.log")
    base = datetime(2026, 9, 28, 14, 0, 0, tzinfo=timezone.utc)

    def stamp(index: int) -> str:
        return (base + timedelta(seconds=index)).isoformat().replace("+00:00", "Z")

    def make(event_id: str, parent: str | None, agent: str, step: str, event_type: str,
             source: str, status: str, inp: dict, out: dict, index: int, links: dict | None = None) -> dict:
        return {
            "schema_version": "agentops-trace-v0.1",
            "run_id": run_id,
            "event_id": event_id,
            "parent_event_id": parent,
            "agent_id": agent,
            "step_id": step,
            "event_type": event_type,
            "timestamp": stamp(index),
            "source": source,
            "status": status,
            "input_summary": inp,
            "output_summary": out,
            "attributes": {"observed_agent_pids": agent_pids, "observed_tool_pids": tool_pids, "observation_links": links or {}},
        }

    trace = [
        make("evt-001", None, "orchestrator", "task.start", "task.start", "probe_manifest", "started", {}, {"item": "alpha", "required_available": 1}, 0),
        make("evt-002", "evt-001", "agent_a", "agent_a.route_write", "file.write", "agentsight+workspace", "success", {}, route, 1, {"agent_pid": agent_pids[0] if agent_pids else None}),
        make("evt-003", "evt-002", "agent_b", "agent_b.route_read", "file.read", "agentsight+workspace", "success", {}, route, 2, {"agent_pid": agent_pids[-1] if agent_pids else None}),
        make("evt-004", "evt-003", "agent_b", "agent_b.bash_tool_call", "tool.call", "agentsight+process", "success", {"tool": "fake_inventory", "item": "alpha"}, {}, 3, {"agent_pid": agent_pids[-1] if agent_pids else None}),
        make("evt-005", "evt-004", "agent_b", "agent_b.tool_result", "tool.result", "agentsight+process", "success", {"tool": "fake_inventory", "item": "alpha"}, {"status": "ok", "item": "alpha", "available": decision.get("observed_available")}, 4, {"tool_pid": tool_pids[0] if tool_pids else None}),
        make("evt-006", "evt-005", "agent_b", "agent_b.decision", "file.write", "agentsight+workspace", "success", {"required_available": route.get("required_available"), "observed_available": decision.get("observed_available")}, decision, 5, {"agent_pid": agent_pids[-1] if agent_pids else None}),
        make("evt-007", "evt-006", "orchestrator", "task.finish", "task.finish", "probe_manifest", "failed", decision, {"success": decision.get("satisfied") is True}, 6),
    ]
    normalized_truth = {
        "schema_version": "agentops-ground-truth-v0.1",
        "run_id": run_id,
        "task_success": False,
        "fault_type": truth.get("fault_type"),
        "responsible_agent": "agent_b",
        "responsible_step": "agent_b.bash_tool_call",
        "responsible_edge": {"from_event_id": "evt-004", "to_event_id": "evt-005"},
        "evidence_event_ids": ["evt-004", "evt-005", "evt-006", "evt-007"],
        "label_source": "fixed probe manifest + workspace artifacts",
    }
    with (args.run_dir / "trace.jsonl").open("w", encoding="utf-8") as handle:
        for item in trace:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    (args.run_dir / "ground_truth-normalized.json").write_text(json.dumps(normalized_truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.run_dir / "normalization-summary.json").write_text(json.dumps({"run_id": run_id, "trace_events": len(trace), "agent_pids": agent_pids, "tool_pids": tool_pids, "source_db": str(args.run_dir / "session.db")}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": run_id, "trace_events": len(trace), "agent_pids": agent_pids, "tool_pids": tool_pids}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
