#!/usr/bin/env python3
"""Create a local PID namespace and record direct NSpid mapping ground truth."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import time


def parse_nspid(status_text: str) -> list[int]:
    for line in status_text.splitlines():
        if line.startswith("NSpid:"):
            values = [int(value) for value in line.split(":", 1)[1].split()]
            if not values or any(value < 1 for value in values):
                raise ValueError("Invalid NSpid vector")
            return values
    raise ValueError("NSpid is absent from process status")


def descendants(pid: int) -> set[int]:
    found, pending = set(), [pid]
    while pending:
        current = pending.pop()
        path = Path(f"/proc/{current}/task/{current}/children")
        if not path.exists():
            continue
        for value in path.read_text(encoding="utf-8").split():
            child = int(value)
            if child not in found:
                found.add(child)
                pending.append(child)
    return found


def wait_for(path: Path, timeout_seconds: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.exists() and path.stat().st_size:
            return
        time.sleep(0.02)
    raise TimeoutError(f"Timed out waiting for {path}")


def capture_ground_truth() -> dict:
    with tempfile.TemporaryDirectory(prefix="agentops-pid-ns-") as temp:
        work = Path(temp)
        inner_pid_file, release_file = work / "inner-pid", work / "release"
        script = (
            f"printf '%s\\n' \"$$\" > '{inner_pid_file}'; "
            f"while [ ! -e '{release_file}' ]; do sleep 0.02; done"
        )
        process = subprocess.Popen([
            "unshare", "--user", "--map-root-user", "--pid", "--fork", "--mount-proc",
            "sh", "-c", script,
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            wait_for(inner_pid_file)
            local_pid = int(inner_pid_file.read_text(encoding="utf-8").strip())
            candidates = sorted(descendants(process.pid) | {process.pid})
            matches = []
            for candidate in candidates:
                status_path = Path(f"/proc/{candidate}/status")
                if not status_path.exists():
                    continue
                vector = parse_nspid(status_path.read_text(encoding="utf-8"))
                if len(vector) >= 2 and vector[-1] == local_pid:
                    matches.append((candidate, vector))
            if len(matches) != 1:
                raise ValueError(f"Expected one outer PID for inner PID {local_pid}, got {matches}")
            observer_pid, vector = matches[0]
            return {
                "schema_version": "agentops-pid-namespace-ground-truth-v0.1",
                "evidence_kind": "runtime_observed_local_fixture",
                "mapping_status": "accepted",
                "mapping_method": "proc_status_nspid",
                "local_pid": local_pid,
                "observer_pid": observer_pid,
                "nspid_vector": vector,
                "observer_pid_matches_vector_head": vector[0] == observer_pid,
                "local_pid_matches_vector_tail": vector[-1] == local_pid,
                "process_pid_namespace": os.readlink(f"/proc/{observer_pid}/ns/pid"),
                "observer_view_pid_namespace": os.readlink("/proc/self/ns/pid"),
                "direct_ground_truth": True,
                "environment": {
                    "system": platform.system(),
                    "kernel_release": platform.release(),
                    "machine": platform.machine(),
                    "python": platform.python_version(),
                    "unshare": subprocess.check_output(
                        ["unshare", "--version"], text=True).strip(),
                },
                "network_calls": 0,
            }
        finally:
            release_file.touch()
            stdout, stderr = process.communicate(timeout=5)
            if process.returncode != 0:
                raise RuntimeError(f"unshare fixture failed: {stderr or stdout}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = capture_ground_truth()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
