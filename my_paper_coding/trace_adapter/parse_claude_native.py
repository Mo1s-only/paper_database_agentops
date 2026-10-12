#!/usr/bin/env python3
"""Convert actually observed native Claude stream records, retaining raw line provenance.

Only system/init, assistant/tool_use, user/tool_result and terminal result are used.
No final-summary reconstruction, prompt-derived tool IDs, or responsibility labels.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from align_candidates import ROOT, sha256, write_json, write_jsonl
from application_events import EventWriter, read_events


def convert_agent(run: Path, agent: str, output: Path):
    launch_path = run / f"{agent}-launch.json"
    timing_path = run / f"{agent}-receipt-times.jsonl"
    raw_path = run / f"claude-agent-{agent[-1]}.log"
    launch = json.loads(launch_path.read_text(encoding="utf-8"))
    receipts = {r["line"]: r for r in [json.loads(s) for s in timing_path.read_text().splitlines()]}
    writer = EventWriter(output / f"{agent}-events.jsonl", run.name, launch["session_id"], agent,
                         launch["process"], launch["clock"], "runtime_observed")
    mappings, seen_tools, ended_tools = [], set(), set()
    initialized = terminated = False
    raw_ref = raw_path.resolve().relative_to(ROOT).as_posix()
    timing_ref = timing_path.resolve().relative_to(ROOT).as_posix()
    launch_ref = launch_path.resolve().relative_to(ROOT).as_posix()

    def emit(kind, line, tool=None):
        event = writer.emit(kind, "native-tool:" + tool if tool else None, tool if kind.startswith("tool.") else None,
                            receipts[line]["received_at_ms"])
        mappings.append({"event_id": event["event_id"], "event_type": kind,
                         "step_id_semantics": "adapter-defined tool span keyed by original tool_call_id; not framework reasoning step",
                         "timestamp_semantics": "local native-stream receipt time, not original tool execution start",
                         "raw_refs": [f"{raw_ref}#line={line}", f"{timing_ref}#line={line}", launch_ref]})

    try:
        for line, text in enumerate(raw_path.read_text(encoding="utf-8").splitlines(), 1):
            native = json.loads(text)
            kind = native.get("type")
            if line not in receipts:
                raise ValueError("Missing stream receipt time")
            sid = native.get("session_id")
            if sid is not None and sid != launch["session_id"]:
                raise ValueError("Native session differs from launched session")
            if kind == "system" and native.get("subtype") == "init":
                if initialized:
                    raise ValueError("Duplicate initialization")
                emit("session.start", line); initialized = True
            elif kind in {"assistant", "user"}:
                message = native.get("message", {})
                content = message.get("content", [])
                if not isinstance(content, list):
                    continue
                for block in content:
                    if block.get("type") == "tool_use" and kind == "assistant":
                        tool = block.get("id")
                        if not tool or tool in seen_tools:
                            raise ValueError("Missing or repeated native tool ID")
                        emit("step.start", line, tool)
                        emit("tool.start", line, tool)
                        seen_tools.add(tool)
                    elif block.get("type") == "tool_result" and kind == "user":
                        tool = block.get("tool_use_id")
                        if tool not in seen_tools or tool in ended_tools:
                            raise ValueError("Unmatched or duplicate tool result")
                        emit("tool.end", line, tool)
                        emit("step.end", line, tool)
                        ended_tools.add(tool)
            elif kind == "result":
                if not initialized or terminated or seen_tools != ended_tools:
                    raise ValueError("Terminal result without a closed tool lifecycle")
                emit("session.end", line); terminated = True
        if not terminated:
            raise ValueError("Native stream lacks terminal result")
        info = writer.finish()
    finally:
        writer.close()
    parsed, _ = read_events(writer.path)
    return parsed, mappings, {**info, "agent_id": agent, "native_tools": len(seen_tools),
                              "raw_sha256": sha256(raw_path), "timing_sha256": sha256(timing_path),
                              "launch_sha256": sha256(launch_path)}


def convert(run: Path, output: Path):
    output.mkdir(parents=True, exist_ok=False)
    events, mappings, reports = [], [], []
    for agent in ("agent_a", "agent_b"):
        parsed, refs, report = convert_agent(run, agent, output)
        events.extend(parsed); mappings.extend(refs); reports.append(report)
    write_jsonl(output / "application-events.jsonl", events)
    write_jsonl(output / "native-event-provenance.jsonl", mappings)
    read_events(output / "application-events.jsonl")
    report = {"run_id": run.name, "agents": reports, "events": len(events),
              "evidence_kind": "runtime_observed", "native_provenance_complete": len(events) == len(mappings),
              "boundary": "Adapter tool spans and stream receipt timestamps; not semantic reasoning steps or causal truth"}
    write_json(output / "native-parser-report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(convert(args.run, args.output), ensure_ascii=False))
