#!/usr/bin/env python3
"""Build a v0.2 application event stream from one real process/clock experiment."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from application_events_v2 import VERSION, event, write_events


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def blocks(row):
    content = row.get("message", {}).get("content", [])
    return content if isinstance(content, list) else []


def anchor_clock(anchor, observer=None, correction_ns=None):
    interval = anchor["realtime_interval_ns"]
    value = {
        "application_realtime_ns": anchor["realtime_midpoint_ns"],
        "application_realtime_interval_ns": interval,
        "application_monotonic_ns": anchor["monotonic_ns"],
        "application_boottime_ns": anchor["boottime_ns"],
        "application_uncertainty_ns": max(
            anchor["realtime_uncertainty_ns"], (interval[1] - interval[0] + 1) // 2),
        "observer_raw_boot_ns": None,
        "observer_epoch_ms": None,
        "observer_boot_epoch_ns": None,
        "observer_anchor_uncertainty_ns": None,
        "conversion": None,
        "correction_ns": None,
    }
    if observer is not None:
        value.update({
            "observer_raw_boot_ns": observer["observer_raw_boot_ns"],
            "observer_epoch_ms": observer["timestamp_ms"],
            "observer_boot_epoch_ns": observer["observer_boot_epoch_ns"],
            "observer_anchor_uncertainty_ns":
                observer["observer_clock_uncertainty_ns"],
            "conversion": "boot_epoch_ns_plus_bpf_ktime_ns",
            "correction_ns": correction_ns,
        })
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, required=True)
    args = parser.parse_args()
    experiment = args.experiment.resolve()
    results = experiment / "results"
    native = [json.loads(line) for line in
              (results / "framework-native.jsonl").read_text(encoding="utf-8").splitlines()]
    receipts = {row["line"]: row for row in
                (json.loads(line) for line in
                 (results / "framework-receipts.jsonl").read_text().splitlines())}
    capture = load_json(results / "capture-summary.json")
    launch = load_json(results / "launch.json")
    scope = load_json(results / "capture-scope.json")
    analysis = load_json(experiment / "analysis.json")

    tool = None
    tool_end_line = None
    result_line = None
    for line_no, row in enumerate(native, 1):
        if row.get("type") == "result":
            result_line = line_no
        for block in blocks(row):
            if block.get("type") == "tool_use":
                tool = {"id": block["id"], "line": line_no}
            elif block.get("type") == "tool_result" and tool and block.get("tool_use_id") == tool["id"]:
                tool_end_line = line_no
    if tool is None or tool_end_line is None or result_line is None:
        raise ValueError("Real native lifecycle is incomplete")

    with sqlite3.connect(f"file:{(results / 'session.db').as_posix()}?mode=ro",
                         uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = [dict(row) for row in connection.execute(
            "SELECT * FROM tool_calls WHERE tool_call_id=?", (tool["id"],))]
    if len(rows) != 1:
        raise ValueError("Expected exactly one AgentSight tool row")
    observer = rows[0]
    required = ("observer_raw_boot_ns", "observer_boot_epoch_ns",
                "observer_clock_uncertainty_ns")
    if any(observer.get(name) is None for name in required):
        raise ValueError("Patched AgentSight raw clock fields are absent")
    if analysis["applied_clock_correction_ns"] != 0:
        raise ValueError("Native nanosecond conversion was not validated")

    process = {
        "host_id": scope["host_id"],
        "boot_id": scope["boot_id"],
        "local_pid": capture["launcher_pid"],
        "local_pid_namespace": launch["pid_namespace"],
        "observer_pid": observer["related_pid"],
        "observer_pid_namespace": scope["observer_pid_namespace"],
        "mapping_status": "inferred",
        "mapping_method": "session+comm+launch_interval+shared_tool_call_id",
        "mapping_evidence": [
            "capture-summary.session_id",
            "process_nodes.comm=claude",
            "analysis.process_start_in_launch_interval=true",
            "tool_calls.tool_call_id=framework.tool_use.id"
        ],
        "start_realtime_interval_ns": [
            launch["launch_before"]["realtime_interval_ns"][0],
            launch["launch_after"]["realtime_interval_ns"][1]
        ],
        "observer_start_epoch_ms": analysis["agentsight_process_start_raw_ms"],
    }
    run_id = experiment.name
    session_id = capture["session_id"]
    base = {
        "schema_version": VERSION,
        "evidence_kind": "runtime_observed",
        "run_id": run_id,
        "session_id": session_id,
        "agent_id": "claude-code-main",
        "process": process,
    }
    step_id = "step-native-bash-1"
    tool_start_clock = anchor_clock(
        receipts[tool["line"]], observer, analysis["applied_clock_correction_ns"])
    events = [
        event(base, "session.start", 0, anchor_clock(launch["launch_before"])),
        event(base, "step.start", 1, anchor_clock(receipts[tool["line"]]),
              step_id=step_id),
        event(base, "tool.start", 2, tool_start_clock, step_id=step_id,
              tool_call_id=tool["id"]),
        event(base, "tool.end", 3, anchor_clock(receipts[tool_end_line]),
              step_id=step_id, tool_call_id=tool["id"]),
        event(base, "step.end", 4, anchor_clock(receipts[tool_end_line]),
              step_id=step_id),
        event(base, "session.end", 5, anchor_clock(receipts[result_line])),
    ]
    output = results / "application-events-v0.2.jsonl"
    stream_summary = write_events(output, events)
    summary = {
        "schema_version": "agentops-application-event-v0.2-build-summary",
        "experiment_id": experiment.name,
        "stream": stream_summary,
        "event_file_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "process_mapping_status": process["mapping_status"],
        "local_pid": process["local_pid"],
        "observer_pid": process["observer_pid"],
        "clock_formula_verified": analysis["agentsight_tool_epoch_formula_verified"],
        "applied_clock_correction_ns": analysis["applied_clock_correction_ns"],
    }
    (experiment / "application-events-v0.2-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
