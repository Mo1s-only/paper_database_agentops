#!/usr/bin/env python3
"""Conservatively link native Claude tool spans to AgentSight runtime evidence.

This adapter runs outside AgentSight. It never edits the source database and
never turns a temporal/process correlation into a direct shared-ID claim.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import shlex
import sqlite3


def json_lines(path: Path):
    for line_no, text in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            yield line_no, value


def norm_path(value: str) -> str:
    return value.replace("\\", "/").rstrip("/").casefold()


def command_tokens(value: str) -> list[str]:
    try:
        return shlex.split(value, posix=True)
    except ValueError:
        return value.split()


def read_tool_spans(run: Path, agent: str) -> list[dict]:
    receipts = {int(row["line"]): row for _, row in json_lines(run / f"{agent}-receipt-times.jsonl")}
    raw_path = run / f"claude-agent-{agent[-1]}.log"
    tools: dict[str, dict] = {}
    for line_no, row in json_lines(raw_path):
        message = row.get("message") if isinstance(row.get("message"), dict) else {}
        blocks = message.get("content", [])
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            if row.get("type") == "assistant" and block.get("type") == "tool_use":
                tool_id = block.get("id")
                if not tool_id or tool_id in tools:
                    raise ValueError(f"Missing or duplicate native tool ID in {raw_path}:{line_no}")
                tools[tool_id] = {
                    "tool_call_id": tool_id,
                    "agent_id": agent,
                    "tool_name": block.get("name"),
                    "input": block.get("input") if isinstance(block.get("input"), dict) else {},
                    "use_line": line_no,
                    "use_receipt_ms": receipts.get(line_no, {}).get("received_at_ms"),
                    "result_line": None,
                    "result_receipt_ms": None,
                }
            elif row.get("type") == "user" and block.get("type") == "tool_result":
                tool_id = block.get("tool_use_id")
                if tool_id in tools and tools[tool_id]["result_line"] is None:
                    tools[tool_id]["result_line"] = line_no
                    tools[tool_id]["result_receipt_ms"] = receipts.get(line_no, {}).get("received_at_ms")
    return list(tools.values())


def load_system_events(run: Path) -> tuple[list[dict], list[dict], dict]:
    raw_events = list(json_lines(run / "raw-stream.log"))
    anchors = [row for _, row in raw_events
               if row.get("data", {}).get("event") == "CLOCK_SYNC"
               and row.get("data", {}).get("phase") == "start"]
    if len(anchors) != 1:
        raise ValueError(f"Expected one start CLOCK_SYNC anchor; found {len(anchors)}")
    anchor = anchors[0]["data"]
    wall_ns, mono_ns = int(anchor["wall_time_ns"]), int(anchor["mono_ns"])
    process_events = []
    for line_no, row in raw_events:
        data = row.get("data", {})
        if row.get("source") != "process" or data.get("event") != "EXEC":
            continue
        event_mono_ns = data.get("timestamp")
        if event_mono_ns is None:
            continue
        process_events.append({
            "source_kind": "agentsight.process_exec",
            "source_file": "raw-stream.log",
            "source_line": line_no,
            "pid": row.get("pid"),
            "ppid": data.get("ppid"),
            "namespace_pid": data.get("namespace_pid"),
            "filename": data.get("filename"),
            "full_command": data.get("full_command", ""),
            "event_mono_ns": int(event_mono_ns),
            "event_wall_ms": (wall_ns + int(event_mono_ns) - mono_ns) / 1_000_000,
        })
    file_events = []
    db = run / "session.db"
    with closing(sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)) as connection:
        for row in connection.execute(
            "SELECT id,timestamp_ms,pid,target,action,details_json "
            "FROM audit_events WHERE audit_type='file' AND action='write'"
        ):
            file_events.append({
                "source_kind": "agentsight.file_audit",
                "source_table": "audit_events",
                "source_row": row[0],
                "event_wall_ms": row[1],
                "pid": row[2],
                "target": row[3],
                "action": row[4],
            })
    return process_events, file_events, {
        "anchor_wall_time_ns": wall_ns,
        "anchor_monotonic_ns": mono_ns,
        "anchor_uncertainty_ns": anchor.get("_agentsight_clock", {}).get("anchor_uncertainty_ns"),
    }


def pid_descends_from(pid: int, root_pid: int, parent_by_pid: dict[int, int | None]) -> bool:
    current = pid
    visited = set()
    while current not in visited:
        visited.add(current)
        if current == root_pid:
            return pid != root_pid
        parent = parent_by_pid.get(current)
        if parent is None:
            return False
        current = int(parent)
    return False


def align(run: Path) -> dict:
    launches = {}
    for agent in ("agent_a", "agent_b"):
        launch_path = run / f"{agent}-launch.json"
        if launch_path.is_file():
            launches[agent] = json.loads(launch_path.read_text(encoding="utf-8"))
    process_events, file_events, clock = load_system_events(run)
    uncertainty_ns = clock.get("anchor_uncertainty_ns")
    uncertainty_ms = float(uncertainty_ns) / 1_000_000 if uncertainty_ns is not None else None
    parent_by_pid = {int(item["pid"]): (int(item["ppid"]) if item.get("ppid") is not None else None)
                     for item in process_events if item.get("pid") is not None}
    links = []
    for agent, launch in launches.items():
        roots = [item for item in process_events
                 if item.get("namespace_pid") == int(launch["pid"])
                 and "claude" in str(item.get("filename", "")).casefold()]
        root_ok = len(roots) == 1
        root_pid = int(roots[0]["pid"]) if root_ok else None
        for tool in read_tool_spans(run, agent):
            start, end = tool.get("use_receipt_ms"), tool.get("result_receipt_ms")
            span_ok = (start is not None and end is not None and end >= start
                       and uncertainty_ms is not None and end - start >= 2 * uncertainty_ms)
            # Convert the anchor's stated uncertainty into a conservative inner
            # interval. Events near either boundary abstain instead of gaining
            # eligibility from a permissive time-window expansion.
            lower, upper = (float(start) + uncertainty_ms, float(end) - uncertainty_ms) \
                if span_ok else (None, None)
            candidates = []
            tool_name = str(tool.get("tool_name", "")).casefold()
            if root_ok and span_ok and tool_name == "bash":
                command = str(tool.get("input", {}).get("command", ""))
                expected = [norm_path(token) for token in command_tokens(command)
                            if token.casefold().endswith(".py") or "/" in token]
                for event in process_events:
                    if event.get("pid") is None or not (lower <= event["event_wall_ms"] <= upper):
                        continue
                    if not pid_descends_from(int(event["pid"]), root_pid, parent_by_pid):
                        continue
                    observed_tokens = [norm_path(token) for token in command_tokens(event["full_command"])]
                    markers = [token for token in expected if token in observed_tokens]
                    if markers:
                        candidates.append({**event, "matched_command_markers": markers})
            elif root_ok and span_ok and tool_name == "write":
                expected_target = norm_path(str(tool.get("input", {}).get("file_path", "")))
                for event in file_events:
                    if event.get("pid") is None or not (lower <= event["event_wall_ms"] <= upper):
                        continue
                    if norm_path(str(event.get("target", ""))) != expected_target:
                        continue
                    if not pid_descends_from(int(event["pid"]), root_pid, parent_by_pid):
                        continue
                    candidates.append(event)
            accepted = len(candidates) == 1
            links.append({
                "tool_call_id": tool["tool_call_id"],
                "agent_id": agent,
                "tool_name": tool.get("tool_name"),
                "semantic_span": {"use_line": tool["use_line"], "result_line": tool["result_line"],
                                  "start_receipt_ms": start, "end_receipt_ms": end},
                "link_status": "unique_runtime_candidate" if accepted else "abstain",
                "relation_evidence": "inferred_unique_pid_ancestry_command_and_time"
                if accepted and tool_name == "bash" else
                "inferred_unique_pid_ancestry_target_and_time" if accepted else None,
                "direct_shared_tool_id": False,
                "checks": {"unique_claude_pid_namespace_root": root_ok,
                           "closed_native_tool_span": span_ok,
                           "same_agent_process_descendant": root_ok and span_ok,
                           "unique_candidate": accepted},
                "candidate_count": len(candidates),
                "runtime_candidates": candidates,
                "limitation": "No shared tool_call_id is emitted in these AgentSight runtime rows; accepted links are corroborated inferences, not direct ID joins.",
            })
    linked = sum(item["link_status"] == "unique_runtime_candidate" for item in links)
    return {
        "schema_version": "semantic-runtime-strict-link-v0.1",
        "run_id": run.name,
        "policy": "Fail closed: require a unique native tool span, a unique AgentSight process root mapped by namespace PID, same-agent descendant process, calibrated event time inside the tool span after contracting both boundaries by anchor uncertainty, and exact command marker or file target.",
        "clock": clock,
        "native_tool_spans": len(links),
        "unique_runtime_candidates": linked,
        "abstentions": len(links) - linked,
        "complete_linkage": bool(links) and linked == len(links),
        "links": links,
        "claim_boundary": "This adapter is outside AgentSight. It never labels a process/time/target correlation as a direct shared-ID relation or causal proof.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = align(args.run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({key: report[key] for key in ("run_id", "native_tool_spans", "unique_runtime_candidates",
                                                   "abstentions", "complete_linkage")}, ensure_ascii=False))
    return 0 if report["complete_linkage"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
