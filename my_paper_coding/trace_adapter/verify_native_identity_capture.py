#!/usr/bin/env python3
"""Verify that an AgentSight process event directly maps to its collector namespace PID."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_events(path: Path) -> list[dict]:
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def evaluate(events: list[dict], target: dict) -> dict:
    marker = target["marker"]
    matches = [event for event in events if marker in json.dumps(event, sort_keys=True)]
    unique = len(matches) == 1
    data = matches[0].get("data", {}) if unique else {}
    clock = data.get("_agentsight_clock", {}) if isinstance(data, dict) else {}
    initial_pid = data.get("pid")
    namespace_pid = data.get("namespace_pid")
    userspace_pid = target.get("userspace_pid")
    checks = {
        "unique_marker_event": unique,
        "exec_event": data.get("event") == "EXEC",
        "initial_namespace_pid_present": isinstance(initial_pid, int) and initial_pid > 0,
        "collector_namespace_pid_present": isinstance(namespace_pid, int) and namespace_pid > 0,
        "collector_namespace_pid_matches_userspace": namespace_pid == userspace_pid,
        "namespace_views_are_distinct": initial_pid != namespace_pid,
        "clock_resolution_floor_nonzero": isinstance(clock.get("anchor_uncertainty_ns"), int)
                                           and clock["anchor_uncertainty_ns"] > 0,
        "native_clock_formula_declared":
            clock.get("conversion") == "boot_epoch_ns_plus_bpf_ktime_ns",
    }
    return {
        "schema_version": "agentops-native-identity-verification-v0.1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "evidence": {
            "marker": marker,
            "userspace_pid": userspace_pid,
            "initial_namespace_pid": initial_pid,
            "collector_namespace_pid": namespace_pid,
            "pid_mapping_status": "accepted" if checks["collector_namespace_pid_matches_userspace"] else "abstain",
            "mapping_method": "bpf_get_ns_current_pid_tgid",
            "observer_raw_boot_ns": clock.get("raw_boot_ns"),
            "observer_boot_epoch_ns": clock.get("boot_epoch_ns"),
            "observer_anchor_uncertainty_ns": clock.get("anchor_uncertainty_ns"),
        },
        "claims": {
            "root_cause_generated": False,
            "responsibility_generated": False,
            "causal_path_generated": False,
        },
        "network_calls": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    target = json.loads(args.target.read_text(encoding="utf-8"))
    result = evaluate(load_events(args.events), target)
    result["input_sha256"] = {
        "events": sha256(args.events),
        "target": sha256(args.target),
    }
    if args.output.exists() and not args.force:
        raise FileExistsError(args.output)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
