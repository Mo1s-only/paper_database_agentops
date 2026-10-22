#!/usr/bin/env python3
"""Zero-API AgentSight/eBPF probe for tagged pipeline/background/multi-process shells."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import time


CASES = [
    ("pipeline", "python3 -c 'print(\"left\")' | cat >/dev/null", 0),
    ("background_wait", "python3 -c 'import time; time.sleep(0.15)' & wait", 0),
    ("two_children", "python3 -c 'pass' && python3 -c 'pass'", 0),
    ("nonzero_exit", "python3 -c 'raise SystemExit(7)'", 7),
]


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stop(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGINT)
    try:
        process.wait(timeout=12)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def read_events(path: Path) -> list[dict]:
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("source") == "process":
            details = row.get("data", {})
            if details.get("event") == "EXEC":
                events.append(row)
    return events


def lineage_reaches(pid: int, carrier_pids: set[int], parent_by_pid: dict[int, int]) -> bool:
    seen = set()
    current = pid
    while current not in seen:
        if current in carrier_pids:
            return True
        seen.add(current)
        if current not in parent_by_pid:
            return False
        current = parent_by_pid[current]
    return False


def run_probe(output: Path, binary: Path, expected_sha256: str) -> dict:
    actual_sha256 = digest_file(binary)
    if actual_sha256.casefold() != expected_sha256.casefold():
        raise ValueError(f"AgentSight SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}")
    output.mkdir(parents=True, exist_ok=False)
    raw_path = output / "raw-process.log"
    raw = raw_path.open("x", encoding="utf-8")
    observer = subprocess.Popen([str(binary), "debug", "process"], stdout=raw,
                                stderr=subprocess.STDOUT, start_new_session=True)
    case_results = []
    try:
        time.sleep(1)
        if observer.poll() is not None:
            raise RuntimeError("AgentSight debug process exited before local probe")
        for index, (name, command, expected_exit) in enumerate(CASES, start=1):
            tool_id = f"call_probe_{index}_{name}"
            marker = f"AGENTOPS_TOOL_CALL_ID={tool_id}"
            wrapped = f"exec -a {shlex.quote(marker)} /bin/bash -c {shlex.quote(command)}"
            result = subprocess.run(["/bin/bash", "-c", wrapped], capture_output=True,
                                    timeout=10, check=False)
            case_results.append({"name": name, "synthetic_tool_call_id": tool_id,
                                 "expected_exit_code": expected_exit,
                                 "observed_exit_code": result.returncode,
                                 "exit_code_matches": result.returncode == expected_exit,
                                 "stdout_bytes": len(result.stdout), "stderr_bytes": len(result.stderr)})
            time.sleep(0.15)
        concurrent_specs = [
            ("concurrent_A", "call_probe_concurrent_A"),
            ("concurrent_B", "call_probe_concurrent_B"),
        ]
        concurrent_processes = []
        concurrent_command = "python3 -c 'import time; time.sleep(0.25)'"
        for name, tool_id in concurrent_specs:
            marker = f"AGENTOPS_TOOL_CALL_ID={tool_id}"
            wrapped = f"exec -a {shlex.quote(marker)} /bin/bash -c {shlex.quote(concurrent_command)}"
            process = subprocess.Popen(["/bin/bash", "-c", wrapped], stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, start_new_session=True)
            concurrent_processes.append((name, tool_id, process))
        for name, tool_id, process in concurrent_processes:
            stdout, stderr = process.communicate(timeout=10)
            case_results.append({"name": name, "synthetic_tool_call_id": tool_id,
                                 "expected_exit_code": 0, "observed_exit_code": process.returncode,
                                 "exit_code_matches": process.returncode == 0,
                                 "stdout_bytes": len(stdout), "stderr_bytes": len(stderr),
                                 "executed_concurrently": True})
        # Negative control: identical family of process, but deliberately no ID marker.
        negative = subprocess.run(["/bin/bash", "-c", "python3 -c 'pass'"],
                                  capture_output=True, timeout=10, check=False)
        case_results.append({"name": "negative_uninstrumented", "synthetic_tool_call_id": None,
                             "expected_exit_code": 0, "observed_exit_code": negative.returncode,
                             "exit_code_matches": negative.returncode == 0,
                             "stdout_bytes": len(negative.stdout), "stderr_bytes": len(negative.stderr)})
        time.sleep(1)
    finally:
        stop(observer)
        raw.close()

    events = read_events(raw_path)
    parent_by_pid = {int(event["pid"]): int(event.get("data", {}).get("ppid", -1))
                     for event in events if event.get("pid") is not None}
    for result in case_results:
        tool_id = result["synthetic_tool_call_id"]
        if tool_id is None:
            result.update({"carrier_pids": [], "linked_execs": [], "status": "negative_control_no_id"})
            continue
        marker = f"AGENTOPS_TOOL_CALL_ID={tool_id}"
        carriers = [event for event in events
                    if marker in event.get("data", {}).get("full_command", "")]
        carrier_pids = {int(event["pid"]) for event in carriers}
        linked = []
        for event in events:
            details = event.get("data", {})
            filename = Path(details.get("filename", "")).name
            if filename not in {"python3", "cat"}:
                continue
            pid = int(event.get("pid", -1))
            if lineage_reaches(pid, carrier_pids, parent_by_pid):
                linked.append({"pid": pid, "ppid": details.get("ppid"), "filename": filename,
                               "command": details.get("full_command", "")[:240]})
        result.update({"carrier_pids": sorted(carrier_pids), "linked_execs": linked,
                       "status": "direct_instrumented_id_lineage" if carrier_pids and linked else "unmatched"})
    concurrent_pids = {}
    for result in case_results:
        if result.get("executed_concurrently"):
            concurrent_pids[result["synthetic_tool_call_id"]] = {
                item["pid"] for item in result.get("linked_execs", [])
            }
    cross_linked_pids = sorted(
        pid for pid in set().union(*concurrent_pids.values())
        if sum(pid in linked for linked in concurrent_pids.values()) > 1
    ) if concurrent_pids else []
    return {
        "schema_version": "agentsight-tool-id-bridge-ebpf-boundary-v0.1",
        "run_id": output.name,
        "api_calls": 0,
        "agentsight_binary": str(binary),
        "agentsight_sha256": actual_sha256,
        "exec_event_count": len(events),
        "cases": case_results,
        "concurrent_cross_linked_pids": cross_linked_pids,
        "concurrent_ids_isolated": len(concurrent_pids) == 2 and not cross_linked_pids
        and all(concurrent_pids.values()),
        "interpretation_limit": (
            "The synthetic marker exercises Linux exec/PPID capture without Claude or a network call. "
            "It validates eBPF visibility and ancestry, not Claude hook concurrency or production semantics."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--agentsight-bin", required=True, type=Path)
    parser.add_argument("--expected-agentsight-sha256", required=True)
    args = parser.parse_args()
    if len(args.expected_agentsight_sha256) != 64:
        parser.error("expected SHA-256 must have 64 hex characters")
    report = run_probe(args.output, args.agentsight_bin, args.expected_agentsight_sha256)
    report_path = args.output / "probe-report.json"
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
