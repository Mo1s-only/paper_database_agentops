#!/usr/bin/env python3
"""Audit controlled Claude tool-ID to AgentSight/eBPF process lineage for a scenario run."""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def read_jsonl_with_lines(path: Path) -> list[tuple[int, dict]]:
    if not path.is_file():
        return []
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append((line_no, value))
    return rows


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze(run: Path) -> dict:
    hook_events = []
    native_tools = {}
    artifact_hashes = {}
    for agent in ("agent_a", "agent_b"):
        agent_hooks = run / f"{agent}-tool-call-hook-events.jsonl"
        if agent_hooks.is_file():
            artifact_hashes[agent_hooks.name] = sha256(agent_hooks)
            hook_events.extend((agent_hooks.name, line, event)
                               for line, event in read_jsonl_with_lines(agent_hooks))
        native_path = run / f"claude-agent-{agent[-1]}.log"
        if native_path.is_file():
            artifact_hashes[native_path.name] = sha256(native_path)
        for line_no, row in read_jsonl_with_lines(native_path):
            for block in row.get("message", {}).get("content", []) or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use" and block.get("id"):
                    native_tools[block["id"]] = {
                        "tool_name": block.get("name"), "agent_id": agent,
                        "source_ref": f"{native_path.name}#line={line_no}",
                    }
    if not hook_events:
        fallback = run / "tool-call-hook-events.jsonl"
        if fallback.is_file():
            artifact_hashes[fallback.name] = sha256(fallback)
            hook_events = [(fallback.name, line, event)
                           for line, event in read_jsonl_with_lines(fallback)]

    with closing(sqlite3.connect(f"file:{run / 'session.db'}?mode=ro", uri=True)) as connection:
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        system_tool_ids = set()
        system_tool_refs = {}
        if "tool_calls" in tables:
            for rowid, ident in connection.execute(
                    "SELECT rowid, tool_call_id FROM tool_calls WHERE tool_call_id IS NOT NULL"):
                system_tool_ids.add(ident)
                system_tool_refs.setdefault(ident, []).append(f"session.db#tool_calls/{rowid}")
        process_rows = connection.execute(
            "SELECT pid,ppid,comm,command FROM process_nodes").fetchall() if "process_nodes" in tables else []
    process_by_pid = {int(row[0]): row for row in process_rows}
    parent_by_pid = {int(row[0]): int(row[1]) for row in process_rows if row[1] is not None}

    bpf_path = run / "raw-stream.log"
    if not bpf_path.is_file():
        bpf_path = run / "raw-process.log"
    bpf_events = read_jsonl(bpf_path)
    if bpf_path.is_file():
        artifact_hashes[bpf_path.name] = sha256(bpf_path)
    db_path = run / "session.db"
    if db_path.is_file():
        artifact_hashes[db_path.name] = sha256(db_path)
    exec_events = [event for event in bpf_events
                   if event.get("source") == "process"
                   and event.get("data", {}).get("event") == "EXEC"]
    links = []
    target_scripts = ("scenario_service_observer.py", "scenario_service_decider.py",
                      "scenario_faulty_router.py", "scenario_route_executor.py",
                      "public_dataset_runtime_probe.py")
    for tool_id, tool in native_tools.items():
        phases = [(name, line, event) for name, line, event in hook_events
                  if event.get("tool_call_id") == tool_id]
        pre = next(((name, line, event) for name, line, event in phases
                    if event.get("hook_event_name") == "PreToolUse"), None)
        post = next(((name, line, event) for name, line, event in reversed(phases)
                     if event.get("hook_event_name") == "PostToolUse"), None)
        marker = f"AGENTOPS_TOOL_CALL_ID={tool_id}"
        carriers = [(line_no, event) for line_no, event in enumerate(bpf_events, 1)
                    if event.get("source") == "process"
                    and event.get("data", {}).get("event") == "EXEC"
                    and marker in event.get("data", {}).get("full_command", "")]
        carrier_pids = {int(event["pid"]) for _, event in carriers if event.get("pid") is not None}
        child_execs = []
        for line_no, event in enumerate(bpf_events, 1):
            details = event.get("data", {})
            pid = int(event.get("pid", -1))
            filename = Path(details.get("filename", "")).name
            command = details.get("full_command", "")
            if filename != "python3" or not any(script in command for script in target_scripts):
                continue
            current = pid
            lineage = []
            seen = set()
            while current in process_by_pid and current not in seen:
                seen.add(current)
                row = process_by_pid[current]
                lineage.append({"pid": current, "ppid": parent_by_pid.get(current), "comm": row[2]})
                if current in carrier_pids:
                    break
                current = parent_by_pid.get(current, -1)
            carrier_ancestor = bool(lineage and lineage[-1]["pid"] in carrier_pids)
            if carrier_ancestor:
                child_execs.append({"pid": pid, "ppid": details.get("ppid"), "filename": filename,
                                    "source_ref": f"{bpf_path.name}#line={line_no}",
                                    "lineage_to_exact_id_carrier": lineage})
        links.append({
            "tool_call_id": tool_id,
            "tool_name": tool["tool_name"],
            "agent_id": tool["agent_id"],
            "hook_pretooluse_observed": bool(pre),
            "hook_posttooluse_observed": bool(post),
            "hook_tagged_bash": bool(pre and pre[2].get("command_tagged")),
            "native_source_ref": tool["source_ref"],
            "hook_pre_source_ref": f"{pre[0]}#line={pre[1]}" if pre else None,
            "hook_post_source_ref": f"{post[0]}#line={post[1]}" if post else None,
            "agentsight_tool_id_exact_match": tool_id in system_tool_ids,
            "agentsight_tool_match_count": len(system_tool_refs.get(tool_id, [])),
            "agentsight_tool_source_ref": (system_tool_refs[tool_id][0]
                                           if len(system_tool_refs.get(tool_id, [])) == 1 else None),
            "ebpf_exact_id_carrier_pids": sorted(carrier_pids),
            "ebpf_exact_id_carrier_source_refs": [f"{bpf_path.name}#line={line}" for line, _ in carriers],
            "ebpf_linked_scenario_child_execs": child_execs,
            "status": ("direct_instrumented_id_to_process_lineage"
                       if pre and pre[2].get("command_tagged") and carrier_pids and child_execs
                       else "semantic_id_only" if tool_id in system_tool_ids
                       else "unmatched"),
        })
    return {
        "schema_version": "agentops-instrumented-tool-process-audit-v0.1",
        "run_id": run.name,
        "evidence_kind": "controlled_hook_instrumentation_and_runtime_observation",
        "native_tool_count": len(native_tools),
        "source_artifacts": artifact_hashes,
        "agentsight_tool_count": len(system_tool_ids),
        "exact_native_agentsight_tool_id_matches": len(set(native_tools) & system_tool_ids),
        "ebpf_exec_event_count": len(exec_events),
        "tool_links": links,
        "interpretation_limit": (
            "A direct ID path is demonstrated only because Claude PreToolUse supplies the tool ID and this controlled hook injects it into a Bash wrapper argv observed by eBPF. This does not mean passive AgentSight natively emits the tool ID on process events."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze(args.run)
    target = args.output or args.run / "tool-id-process-audit.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
