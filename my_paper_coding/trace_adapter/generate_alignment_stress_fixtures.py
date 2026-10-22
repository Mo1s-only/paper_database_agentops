#!/usr/bin/env python3
"""Generate deterministic, explicitly synthetic identity-linkage stress fixtures.

These fixtures test fail-closed identity decisions; they are not AgentSight runs,
API tasks, or evidence of real-world capture/attribution accuracy.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


CATEGORIES = (
    "valid_unique_pair",
    "missing_system_observation",
    "duplicate_system_id",
    "cross_session_collision",
    "pid_namespace_conflict",
    "clock_outside_tolerance",
    "empty_tool_result",
    "missing_protocol_field",
    "source_hash_mismatch",
)


def make_fixture(index: int) -> dict:
    category = CATEGORIES[index % len(CATEGORIES)]
    app = {
        "run_id": f"synthetic-run-{index:04d}",
        "session_id": f"session-{index % 2}",
        "agent_id": f"agent-{index % 2}",
        "tool_call_id": f"tool-{index:04d}",
        "host_id": "fixture-host",
        "boot_id": "fixture-boot",
        "pid_namespace": "pid:[fixture]",
        "timestamp_ms": 10_000 + index * 100,
        "uncertainty_ms": 5,
        "protocol_complete": True,
        "source_hash": f"sha256:fixture-{index:04d}",
        "tool_result": "ok",
    }
    system = {
        "run_id": app["run_id"],
        "session_id": app["session_id"],
        "tool_call_id": app["tool_call_id"],
        "host_id": app["host_id"],
        "boot_id": app["boot_id"],
        "pid_namespace": app["pid_namespace"],
        "timestamp_ms": app["timestamp_ms"] + 2,
        "source_hash": app["source_hash"],
    }
    systems = [system]
    if category == "missing_system_observation":
        systems = []
    elif category == "duplicate_system_id":
        systems.append(dict(system))
    elif category == "cross_session_collision":
        system["session_id"] = "other-session"
    elif category == "pid_namespace_conflict":
        system["pid_namespace"] = "pid:[other]"
    elif category == "clock_outside_tolerance":
        system["timestamp_ms"] += 100
    elif category == "empty_tool_result":
        app["tool_result"] = ""
    elif category == "missing_protocol_field":
        del app["boot_id"]
    elif category == "source_hash_mismatch":
        system["source_hash"] = "sha256:other-source"
    return {
        "fixture_id": f"fixture-{index:04d}",
        "evidence_kind": "synthetic_fixture",
        "category": category,
        "application": app,
        "system_candidates": systems,
        "expected_status": "accepted" if category == "valid_unique_pair" else
        ("abstain" if category == "missing_system_observation" else "uncertain"),
    }


def decide(fixture: dict) -> tuple[str, str]:
    """Minimal fail-closed fixture oracle, not the production aligner."""
    app = fixture["application"]
    required = {"run_id", "session_id", "agent_id", "tool_call_id", "host_id",
                "boot_id", "pid_namespace", "timestamp_ms", "uncertainty_ms",
                "protocol_complete", "source_hash", "tool_result"}
    if not required.issubset(app) or not app["protocol_complete"]:
        return "uncertain", "incomplete_application_protocol"
    if not fixture["system_candidates"]:
        return "abstain", "system_observation_missing"
    candidates = [r for r in fixture["system_candidates"]
                  if r.get("tool_call_id") == app["tool_call_id"]]
    if not candidates:
        return "abstain", "shared_tool_id_missing"
    if len(candidates) != 1:
        return "uncertain", "duplicate_system_tool_id"
    system = candidates[0]
    if any(system.get(k) != app.get(k) for k in ("run_id", "session_id", "host_id", "boot_id")):
        return "uncertain", "scope_conflict"
    if system.get("pid_namespace") != app["pid_namespace"]:
        return "uncertain", "pid_namespace_conflict"
    if abs(system.get("timestamp_ms", -10**12) - app["timestamp_ms"]) > app["uncertainty_ms"]:
        return "uncertain", "clock_outside_tolerance"
    if system.get("source_hash") != app["source_hash"]:
        return "uncertain", "source_hash_mismatch"
    if not app["tool_result"]:
        return "uncertain", "empty_tool_result"
    return "accepted", "unique_scoped_pair"


def generate(count: int) -> tuple[list[dict], dict]:
    if count <= 0:
        raise ValueError("count must be positive")
    fixtures = [make_fixture(index) for index in range(count)]
    category_counts = Counter(row["category"] for row in fixtures)
    status_counts = Counter()
    mismatches = []
    for row in fixtures:
        status, reason = decide(row)
        status_counts[status] += 1
        if status != row["expected_status"]:
            mismatches.append({"fixture_id": row["fixture_id"], "expected": row["expected_status"],
                               "actual": status, "reason": reason})
    summary = {"evidence_kind": "synthetic_fixture", "fixture_count": count,
               "category_counts": dict(sorted(category_counts.items())),
               "decision_counts": dict(sorted(status_counts.items())),
               "expected_status_mismatches": mismatches,
               "production_aligner_exercised": False,
               "api_calls": 0,
               "limitation": "Deterministic fixture-oracle check only; not production alignment or real capture accuracy."}
    return fixtures, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"refusing to overwrite existing file: {args.output}")
    fixtures, summary = generate(args.count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        for row in fixtures:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if not summary["expected_status_mismatches"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
