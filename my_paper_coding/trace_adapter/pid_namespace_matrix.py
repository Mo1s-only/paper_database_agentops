#!/usr/bin/env python3
"""Run concurrent local PID namespaces and evaluate accepted/inferred/abstain decisions."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile

from pid_namespace_fixture import descendants, parse_nspid, wait_for
from process_identity import decide_pid_mapping


def start_namespace(work: Path, label: str) -> dict:
    inner_pid_file = work / f"{label}-inner-pid"
    release_file = work / f"{label}-release"
    script = (
        f"printf '%s\\n' \"$$\" > '{inner_pid_file}'; "
        f"while [ ! -e '{release_file}' ]; do sleep 0.02; done"
    )
    process = subprocess.Popen([
        "unshare", "--user", "--map-root-user", "--pid", "--fork", "--mount-proc",
        "sh", "-c", script,
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return {"label": label, "process": process, "inner_pid_file": inner_pid_file,
            "release_file": release_file}


def resolve_namespace(item: dict) -> dict:
    wait_for(item["inner_pid_file"])
    local_pid = int(item["inner_pid_file"].read_text(encoding="utf-8").strip())
    matches = []
    for observer_pid in sorted(descendants(item["process"].pid) | {item["process"].pid}):
        status = Path(f"/proc/{observer_pid}/status")
        if not status.exists():
            continue
        vector = parse_nspid(status.read_text(encoding="utf-8"))
        if len(vector) >= 2 and vector[-1] == local_pid:
            matches.append((observer_pid, vector))
    if len(matches) != 1:
        raise ValueError(f"Expected one mapping for {item['label']}, got {matches}")
    observer_pid, vector = matches[0]
    return {
        "label": item["label"], "local_pid": local_pid, "observer_pid": observer_pid,
        "nspid_vector": vector,
        "process_pid_namespace": os.readlink(f"/proc/{observer_pid}/ns/pid"),
        "observer_pid_namespace": os.readlink("/proc/self/ns/pid"),
        "indirect_match": False,
    }


def run_matrix() -> dict:
    with tempfile.TemporaryDirectory(prefix="agentops-pid-matrix-") as temp:
        work = Path(temp)
        items = [start_namespace(work, label) for label in ("a", "b")]
        try:
            candidates = [resolve_namespace(item) for item in items]
            same_local_pid = len({value["local_pid"] for value in candidates}) == 1
            distinct_observer_pids = len({value["observer_pid"] for value in candidates}) == 2
            distinct_process_namespaces = len(
                {value["process_pid_namespace"] for value in candidates}) == 2
            accepted = [decide_pid_mapping(
                value["local_pid"], value["process_pid_namespace"], candidates)
                for value in candidates]
            ambiguous = decide_pid_mapping(candidates[0]["local_pid"], None, candidates)
            indirect_candidate = {
                "observer_pid": 1758,
                "observer_pid_namespace": "linux-initial-pid-namespace",
                "process_pid_namespace": None,
                "nspid_vector": None,
                "indirect_match": True,
            }
            inferred = decide_pid_mapping(
                81, "pid:[4026532214]", [indirect_candidate],
                ["capture-summary.session_id", "process_nodes.comm=claude",
                 "analysis.process_start_in_launch_interval=true",
                 "tool_calls.tool_call_id=framework.tool_use.id"])
            statuses = [value["mapping_status"] for value in accepted] + [
                ambiguous["mapping_status"], inferred["mapping_status"]]
            return {
                "schema_version": "agentops-pid-namespace-matrix-v0.1",
                "evidence_kind": "runtime_observed_local_fixture",
                "concurrent_namespace_count": 2,
                "same_local_pid": same_local_pid,
                "distinct_observer_pids": distinct_observer_pids,
                "distinct_process_namespaces": distinct_process_namespaces,
                "candidates": candidates,
                "decisions": {
                    "namespace_scoped_direct": accepted,
                    "local_pid_only_ambiguous": ambiguous,
                    "unique_indirect_real_shape": inferred,
                },
                "status_counts": {name: statuses.count(name)
                                  for name in ("accepted", "inferred", "abstain")},
                "acceptance_passed": (
                    same_local_pid and distinct_observer_pids and distinct_process_namespaces and
                    all(value["mapping_status"] == "accepted" for value in accepted) and
                    ambiguous["mapping_status"] == "abstain" and
                    inferred["mapping_status"] == "inferred"
                ),
                "environment": {
                    "system": platform.system(), "kernel_release": platform.release(),
                    "machine": platform.machine(), "python": platform.python_version(),
                },
                "network_calls": 0,
            }
        finally:
            for item in items:
                item["release_file"].touch()
            for item in items:
                stdout, stderr = item["process"].communicate(timeout=5)
                if item["process"].returncode != 0:
                    raise RuntimeError(f"namespace {item['label']} failed: {stderr or stdout}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = run_matrix()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["acceptance_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
