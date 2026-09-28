#!/usr/bin/env python3
"""Adapt a TraceElephant task directory to the local v0.1 trace schema."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def status_from_metadata(value: object) -> str:
    text = str(value or "").lower()
    return "success" if any(token in text for token in ("pass", "success", "solved")) else "failed"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    metadata = json.loads((args.task_dir / "trace_metadata.json").read_text(encoding="utf-8"))
    steps = json.loads((args.task_dir / "step_records.json").read_text(encoding="utf-8"))
    if not isinstance(steps, list):
        raise ValueError("step_records.json must contain a list")
    run_id = args.run_id or args.task_dir.name
    base = datetime(1970, 1, 1, tzinfo=timezone.utc)
    trace = []
    previous = None
    for index, step in enumerate(steps, start=1):
        event_id = f"step-{index:04d}"
        stamp = (base + timedelta(seconds=index)).isoformat().replace("+00:00", "Z")
        trace.append({
            "schema_version": "agentops-trace-v0.1",
            "run_id": run_id,
            "event_id": event_id,
            "parent_event_id": previous,
            "agent_id": step.get("agent_name", "unknown"),
            "step_id": str(step.get("step_id", index)),
            "event_type": "agent.step",
            "timestamp": stamp,
            "source": "traceelephant_step_records",
            "status": "success",
            "input_summary": step.get("input", {}),
            "output_summary": step.get("output", ""),
            "attributes": {"external_dataset": "TraceElephant"},
        })
        previous = event_id
    final_id = f"step-{len(steps) + 1:04d}"
    trace.append({
        "schema_version": "agentops-trace-v0.1",
        "run_id": run_id,
        "event_id": final_id,
        "parent_event_id": previous,
        "agent_id": "orchestrator",
        "step_id": "task.finish",
        "event_type": "task.finish",
        "timestamp": (base + timedelta(seconds=len(steps) + 1)).isoformat().replace("+00:00", "Z"),
        "source": "traceelephant_metadata",
        "status": status_from_metadata(metadata.get("tests_status")),
        "input_summary": {"question": metadata.get("task_instruction", "")},
        "output_summary": {"ground_truth": metadata.get("ground_truth", "")},
        "attributes": {"external_dataset": "TraceElephant"},
    })
    truth = {
        "schema_version": "agentops-ground-truth-v0.1",
        "run_id": run_id,
        "task_success": trace[-1]["status"] == "success",
        "fault_type": "external_traceelephant_label",
        "responsible_agent": metadata.get("mistake_agent") or None,
        "responsible_step": str(metadata.get("mistake_step")) if metadata.get("mistake_step") is not None else None,
        "responsible_edge": None,
        "evidence_event_ids": [],
        "label_source": "TraceElephant trace_metadata.json",
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with (args.out_dir / "trace.jsonl").open("w", encoding="utf-8") as handle:
        for item in trace:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    (args.out_dir / "ground_truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": run_id, "trace_events": len(trace), "label_source": truth["label_source"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
