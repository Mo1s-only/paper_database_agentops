#!/usr/bin/env python3
"""Post-process one real canary without any API calls or raw secret output."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3

from analyze_framework_process_clock import choose_native_pid_mapping
from process_identity import decide_pid_mapping


PROMPT_MARKERS = (
    "Use Bash exactly once to run python3",  # run33–run38
    "Use Bash exactly once to run this compound command: python3",  # run39+
)


def analyze(run: Path) -> dict:
    launch = json.loads((run / "agent_a-launch.json").read_text(encoding="utf-8"))
    capture = json.loads((run / "agent_a-capture-summary.json").read_text(encoding="utf-8"))
    events = []
    for line in (run / "raw-process.log").read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    anchors = [event for event in events if event.get("data", {}).get("event") == "CLOCK_SYNC"
               and event["data"].get("phase") == "start"]
    matches = [event for event in events if event.get("source") == "process"
               and event.get("data", {}).get("event") == "EXEC"
               and any(marker in event["data"].get("full_command", "")
                       for marker in PROMPT_MARKERS)]
    if len(anchors) != 1 or len(matches) != 1:
        raise ValueError(f"Expected one clock anchor and one uniquely identified CLI exec, got {len(anchors)}, {len(matches)}")
    anchor, match = anchors[0], matches[0]
    anchor_ns = int(anchor["data"]["wall_time_ns"])
    anchor_mono_ns = int(anchor["data"]["mono_ns"])
    exec_mono_ns = int(match["data"]["timestamp"])
    reconstructed_ms = (anchor_ns + exec_mono_ns - anchor_mono_ns) / 1_000_000
    reported_ms = float(match["timestamp"])
    launch_interval = launch["launch_interval_ms"]
    raw_pid = int(match["pid"])

    with sqlite3.connect(f"file:{run / 'session.db'}?mode=ro", uri=True) as connection:
        rows = connection.execute("SELECT pid,ppid,comm,command FROM process_nodes").fetchall()
        network = connection.execute("SELECT host,path,count FROM network_targets").fetchall()
        exec_audit = connection.execute(
            "SELECT pid,details_json FROM audit_events WHERE audit_type='process' AND action='exec' AND pid=?",
            (raw_pid,),
        ).fetchall()
        audit_types = dict(connection.execute("SELECT audit_type,count(*) FROM audit_events GROUP BY audit_type"))
        counts = {name: connection.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
                  for name in ("llm_calls", "tool_calls", "token_usage", "network_targets", "process_nodes", "audit_events")}
        response_body_values = [row[0] for row in connection.execute("SELECT response_body_json FROM llm_calls")]
        response_bodies_observed = sum(value not in (None, "", "null") for value in response_body_values)
        agent_sight_tool_ids = {row[0] for row in connection.execute(
            "SELECT tool_call_id FROM tool_calls WHERE tool_call_id IS NOT NULL")}
    by_parent: dict[int, list[tuple]] = {}
    process_by_pid: dict[int, tuple] = {}
    for row in rows:
        by_parent.setdefault(row[1], []).append(row)
        process_by_pid[int(row[0])] = row
    descendants = []
    pending = [raw_pid]
    seen = set(pending)
    while pending:
        parent = pending.pop(0)
        for row in by_parent.get(parent, []):
            descendants.append({"pid": row[0], "ppid": row[1], "comm": row[2]})
            if row[0] not in seen:
                pending.append(row[0]); seen.add(row[0])
    receipts = {}
    receipt_path = run / "agent_a-receipt-times.jsonl"
    if receipt_path.is_file():
        for line in receipt_path.read_text(encoding="utf-8").splitlines():
            try:
                receipt = json.loads(line)
                receipts[int(receipt["line"])] = receipt
            except (ValueError, KeyError, TypeError):
                continue
    native_tools_by_id = {}
    for line_no, line in enumerate((run / "claude-agent-a.log").read_text(encoding="utf-8").splitlines(), 1):
        item = json.loads(line)
        content = item.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if item.get("type") == "assistant" and block.get("type") == "tool_use":
                tool_id = block.get("id")
                if tool_id:
                    native_tools_by_id.setdefault(tool_id, {
                        "id": tool_id, "name": block.get("name"), "use_line": line_no,
                        "result_line": None,
                    })
            elif item.get("type") == "user" and block.get("type") == "tool_result":
                tool_id = block.get("tool_use_id")
                if tool_id in native_tools_by_id:
                    native_tools_by_id[tool_id]["result_line"] = line_no
    native_tools = list(native_tools_by_id.values())
    native_tool_ids = {tool["id"] for tool in native_tools}
    exact_tool_id_matches = sorted(native_tool_ids & agent_sight_tool_ids)
    hook_events = []
    hook_event_path = run / "tool-call-hook-events.jsonl"
    if hook_event_path.is_file():
        for line in hook_event_path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    hook_events.append(item)
            except json.JSONDecodeError:
                continue
    descendant_pids = {int(item["pid"]) for item in descendants}
    exec_events_by_pid: dict[int, list[dict]] = {}
    for event in events:
        if event.get("source") == "process" and event.get("data", {}).get("event") == "EXEC":
            exec_events_by_pid.setdefault(int(event["pid"]), []).append(event)

    def process_lineage(pid: int) -> list[dict]:
        """Return the observed PID -> PPID chain, stopping at the Claude launcher."""
        chain = []
        seen_pids = set()
        current = pid
        while current in process_by_pid and current not in seen_pids:
            seen_pids.add(current)
            row = process_by_pid[current]
            exec_observations = exec_events_by_pid.get(current, [])
            latest_details = exec_observations[-1].get("data", {}) if exec_observations else {}
            chain.append({
                "pid": current,
                "ppid": int(row[1]),
                "comm": row[2],
                "exec_observations": [
                    {
                        "comm": item.get("data", {}).get("comm"),
                        "executable": Path(item.get("data", {}).get("filename", "")).name or None,
                    }
                    for item in exec_observations
                ],
                "latest_executable": Path(latest_details.get("filename", "")).name or None,
            })
            if current == raw_pid:
                break
            current = int(row[1])
        return chain

    tool_process_correlations = []
    expected_tool_processes = [event for event in events
        if event.get("source") == "process"
        and event.get("data", {}).get("event") == "EXEC"
        and Path(event.get("data", {}).get("filename", "")).name == "python3"
        and "scenario_service_observer.py" in event.get("data", {}).get("full_command", "")
        and int(event.get("pid", -1)) in descendant_pids]
    for tool in native_tools:
        use_receipt = receipts.get(tool["use_line"], {})
        result_receipt = receipts.get(tool["result_line"], {}) if tool["result_line"] else {}
        start_ms = use_receipt.get("received_at_ms")
        end_ms = result_receipt.get("received_at_ms")
        candidates = []
        if start_ms is not None and end_ms is not None:
            for event in expected_tool_processes:
                details = event.get("data", {})
                event_wall_ms = (anchor_ns + int(details["timestamp"]) - anchor_mono_ns) / 1_000_000
                if start_ms <= event_wall_ms <= end_ms:
                    lineage = process_lineage(int(event["pid"]))
                    lineage_reaches_launcher = bool(lineage and lineage[-1]["pid"] == raw_pid)
                    candidates.append({
                        "observer_pid": int(event["pid"]),
                        "parent_pid": details.get("ppid"),
                        "namespace_pid": details.get("namespace_pid"),
                        "executable": Path(details.get("filename", "")).name,
                        "clock_reconstructed_ms": round(event_wall_ms, 3),
                        "process_lineage_to_claude_launcher": lineage,
                        "lineage_reaches_claude_launcher": lineage_reaches_launcher,
                    })
        hook_observed = any(item.get("tool_call_id") == tool["id"]
                            and item.get("hook_event_name") == "PreToolUse"
                            and item.get("command_tagged") is True for item in hook_events)
        tagged_pids_by_candidate = {}
        marker = f"AGENTOPS_TOOL_CALL_ID={tool['id']}"
        for candidate in candidates:
            candidate_pid = candidate["observer_pid"]
            lineage_pids = {node["pid"] for node in candidate["process_lineage_to_claude_launcher"]}
            tagged_pids_by_candidate[candidate_pid] = sorted(
                pid for pid in lineage_pids
                if any(marker in event.get("data", {}).get("full_command", "")
                       for event in exec_events_by_pid.get(pid, []))
            )
            candidate["ebpf_exec_lineage_pids_with_injected_exact_tool_call_id"] = tagged_pids_by_candidate[candidate_pid]
        tagged_ancestor_pids = sorted({pid for pids in tagged_pids_by_candidate.values() for pid in pids})
        direct_instrumented_id_lineage = (
            hook_observed and bool(candidates)
            and all(candidate["lineage_reaches_claude_launcher"]
                    and tagged_pids_by_candidate.get(candidate["observer_pid"])
                    for candidate in candidates)
        )
        unique_lineage = len(candidates) == 1 and candidates[0]["lineage_reaches_claude_launcher"]
        tool_process_correlations.append({
            "tool_call_id": tool["id"], "tool_name": tool["name"],
            "tool_use_line": tool["use_line"], "tool_result_line": tool["result_line"],
            "candidate_processes": candidates,
            "candidate_count": len(candidates),
            "pretooluse_hook_observed_exact_tool_call_id": hook_observed,
            "ebpf_exec_lineage_pids_with_injected_exact_tool_call_id": tagged_ancestor_pids,
            "status": ("direct_instrumented_id_lineage" if direct_instrumented_id_lineage
                       else "inferred_unique_lineage_and_tool_window_candidate" if unique_lineage
                       else "inferred_unique_command_and_time_candidate" if len(candidates) == 1
                       else "ambiguous" if len(candidates) > 1 else "unmatched"),
            "identity_limit": (
                "The exact tool_call_id was injected by the PreToolUse hook into an ancestor shell command and observed in its eBPF EXEC argv; the concrete child PID is linked by PPID. This is a direct ID bridge only for this instrumented canary, not passive/native eBPF behavior."
                if direct_instrumented_id_lineage else
                "The command is in the Claude launcher descendant tree and inside this tool's observed start/result window, but the eBPF event has no shared tool_call_id; this remains a structural/time inference, not a direct ID join."
            ),
        })
    # Reuse the thesis' existing conservative identity policy. Direct BPF
    # namespace-PID evidence can establish the launcher mapping; tool execution
    # remains a separate, weaker command/clock candidate without a shared ID.
    bpf_namespace_pids = sorted({details.get("namespace_pid") for _, payload in exec_audit
                                 if (details := json.loads(payload or "{}")).get("namespace_pid")})
    direct = choose_native_pid_mapping(
        [{"pid": pid, "action": "exec", "details_json": payload}
         for pid, payload in exec_audit], int(launch["pid"]), [raw_pid])
    if direct["status"] == "accepted":
        pid_mapping = {
            "mapping_status": "accepted", "mapping_method": direct["method"],
            "mapping_evidence": direct["evidence"], "observer_pid": direct["observer_pid"],
            "reason": "unique_direct_bpf_namespace_pid", "candidate_count": direct["candidate_count"],
        }
    else:
        # This run has no shared native/system tool-call ID, so the existing
        # indirect evidence rule must abstain even with a unique command/time.
        pid_mapping = decide_pid_mapping(
            int(launch["pid"]), launch["pid_views"]["pid_namespace_link"],
            [{"observer_pid": raw_pid, "indirect_match": False}])
    result = {
        "kind": "real_api_ebpf_post_analysis",
        "verified": {
            "cli_success": capture["success"],
            "reported_cost_usd": capture["reported_cost_usd"],
            "launcher_pid_in_namespace": launch["pid"],
            "launcher_pid_namespace": launch["pid_views"]["pid_namespace_link"],
            "ebpf_exec_pid": raw_pid,
            "ebpf_exec_command_marker_matched": True,
            "ebpf_exec_clock_reconstructed_ms": reconstructed_ms,
            "launcher_interval_ms": launch_interval,
            "clock_reconstruction_within_launch_interval": launch_interval[0] <= reconstructed_ms <= launch_interval[1] + 2,
            "ebpf_reported_timestamp_ms": reported_ms,
            "reported_minus_reconstructed_ms": round(reported_ms - reconstructed_ms, 3),
            "ebpf_pid_found_in_database": any(row[0] == raw_pid for row in rows),
            "bpf_namespace_pid_values": bpf_namespace_pids,
            "pid_mapping_under_existing_policy": pid_mapping,
            "descendant_comms": sorted({entry["comm"] for entry in descendants}),
            "native_tool_names": [tool["name"] for tool in native_tools],
            "native_tool_count": len(native_tools),
            "native_tool_ids_exactly_present_in_agentsight": len(exact_tool_id_matches) == len(native_tool_ids),
            "exact_tool_id_match_count": len(exact_tool_id_matches),
            "response_bodies_observed": response_bodies_observed,
            "native_tool_process_correlations": tool_process_correlations,
            "handoff_file_exists": (run / "workspace/handoff.json").is_file(),
            "database_counts": counts,
            "audit_types": audit_types,
            "network_targets": [{"host": host, "path": path, "count": count} for host, path, count in network],
            "system_events_persisted_semantic_tables_empty": counts["process_nodes"] > 0
            and counts["audit_events"] > 0 and counts["llm_calls"] == 0 and counts["tool_calls"] == 0,
        },
        "inferred": {
            "unique_command_and_clock_support_candidate_relation": raw_pid != launch["pid"]
            and launch_interval[0] <= reconstructed_ms <= launch_interval[1] + 2,
        },
        "unverified": [
            "The tool_use-to-exec relation has no shared ID and remains a unique command/time inference, not a direct join.",
        ] + ([
            "At least one successful LLM response body was not persisted, so SSE body evidence is incomplete for this run.",
        ] if response_bodies_observed < counts["llm_calls"] else []) + ([
            "Claude native tool_use IDs were observed but AgentSight tool_calls contains no exact matching IDs.",
        ] if native_tool_ids - agent_sight_tool_ids else []) + ([
            "AgentSight token_usage is empty despite a successfully captured LLM response.",
        ] if counts["token_usage"] == 0 and response_bodies_observed > 0 else []),
    }
    (run / "post-analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    print(json.dumps(analyze(parser.parse_args().run.resolve()), ensure_ascii=False))
