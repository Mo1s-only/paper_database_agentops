#!/usr/bin/env python3
"""Run a zero-API publication-quality gate over an application event stream."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import platform

from application_events_v2 import canonicalize_events, read_events, validate_stream, write_events


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mapping_coverage(events: list[dict]) -> dict:
    sessions = {}
    event_counts = {name: 0 for name in ("accepted", "inferred", "abstain")}
    for value in events:
        status = value["process"]["mapping_status"]
        event_counts[status] += 1
        sessions.setdefault(value["session_id"], status)
        if sessions[value["session_id"]] != status:
            raise ValueError("Mapping status changed inside one session")
    session_counts = {name: 0 for name in event_counts}
    for status in sessions.values():
        session_counts[status] += 1
    total = len(sessions)
    return {
        "session_counts": session_counts,
        "event_counts": event_counts,
        "session_total": total,
        "accepted_session_coverage": session_counts["accepted"] / total if total else 0.0,
        "supported_inference_session_coverage": session_counts["inferred"] / total if total else 0.0,
        "abstain_session_coverage": session_counts["abstain"] / total if total else 0.0,
        "accuracy_status": "UNVERIFIED_WITHOUT_INDEPENDENT_PID_GROUND_TRUTH",
    }


def clock_quality(events: list[dict]) -> dict:
    observed = [value for value in events
                if value["clock"]["observer_raw_boot_ns"] is not None]
    zero = [value["event_id"] for value in observed
            if value["clock"]["observer_anchor_uncertainty_ns"] == 0]
    nonzero = [value["event_id"] for value in observed
               if value["clock"]["observer_anchor_uncertainty_ns"] > 0]
    return {
        "observer_clock_event_count": len(observed),
        "nonzero_uncertainty_event_count": len(nonzero),
        "zero_uncertainty_event_count": len(zero),
        "zero_uncertainty_event_ids": zero,
        "resolution_floor_gate_passed": bool(observed) and not zero,
    }


def field_completeness(events: list[dict]) -> dict:
    groups = {
        "event_identity": (events, ("run_id", "event_id", "session_id", "agent_id",
                                    "event_type", "sequence")),
        "process_scope": ([value["process"] for value in events],
                          ("host_id", "boot_id", "local_pid", "local_pid_namespace",
                           "mapping_status", "mapping_evidence", "start_realtime_interval_ns")),
        "application_clock": ([value["clock"] for value in events],
                              ("application_realtime_ns", "application_realtime_interval_ns",
                               "application_monotonic_ns", "application_boottime_ns",
                               "application_uncertainty_ns")),
    }
    measurements = {}
    present_total = expected_total = 0
    for name, (rows, fields) in groups.items():
        expected = len(rows) * len(fields)
        present = sum(value.get(field) is not None for value in rows for field in fields)
        measurements[name] = {"present": present, "expected": expected,
                              "rate": present / expected if expected else 1.0}
        present_total += present; expected_total += expected
    tool_starts = [value for value in events if value["event_type"] == "tool.start"]
    observer_fields = ("observer_raw_boot_ns", "observer_epoch_ms", "observer_boot_epoch_ns",
                       "observer_anchor_uncertainty_ns", "conversion", "correction_ns")
    expected = len(tool_starts) * len(observer_fields)
    present = sum(value["clock"].get(field) is not None
                  for value in tool_starts for field in observer_fields)
    measurements["tool_start_observer_clock"] = {
        "present": present, "expected": expected,
        "rate": present / expected if expected else 1.0,
    }
    present_total += present; expected_total += expected
    lifecycle = {}
    expected_kinds = {"session.start", "step.start", "tool.start", "tool.end",
                      "step.end", "session.end"}
    for session_id in {value["session_id"] for value in events}:
        kinds = {value["event_type"] for value in events if value["session_id"] == session_id}
        lifecycle[session_id] = sorted(expected_kinds - kinds)
    return {
        "groups": measurements,
        "overall_present": present_total,
        "overall_expected": expected_total,
        "overall_rate": present_total / expected_total if expected_total else 1.0,
        "lifecycle_missing_by_session": lifecycle,
        "all_required_lifecycle_kinds_present": all(not missing for missing in lifecycle.values()),
    }


def negative_cases(events: list[dict]):
    def duplicate_event_id(values):
        values[1]["event_id"] = values[0]["event_id"]

    def sequence_gap(values):
        values[1]["sequence"] += 1

    def changed_process_identity(values):
        values[1]["process"]["observer_pid"] += 1

    def missing_tool_end(values):
        del values[3]
        for sequence, value in enumerate(values):
            value["sequence"] = sequence

    def inconsistent_observer_formula(values):
        values[2]["clock"]["observer_epoch_ms"] += 1

    def partial_observer_clock(values):
        values[2]["clock"]["observer_boot_epoch_ns"] = None

    def duplicate_tool_start(values):
        values[3]["event_type"] = "tool.start"

    def backwards_application_clock(values):
        values[-1]["clock"]["application_realtime_ns"] = 0
        values[-1]["clock"]["application_realtime_interval_ns"] = [0, 0]
        values[-1]["clock"]["application_uncertainty_ns"] = 0

    return {
        "duplicate_event_id": duplicate_event_id,
        "sequence_gap": sequence_gap,
        "changed_process_identity": changed_process_identity,
        "missing_tool_end": missing_tool_end,
        "inconsistent_observer_formula": inconsistent_observer_formula,
        "partial_observer_clock": partial_observer_clock,
        "duplicate_tool_start": duplicate_tool_start,
        "backwards_application_clock": backwards_application_clock,
    }


def run_negative_matrix(events: list[dict]) -> dict:
    cases = []
    for name, mutate in negative_cases(events).items():
        values = copy.deepcopy(events)
        mutate(values)
        try:
            validate_stream(values)
        except (TypeError, ValueError) as error:
            cases.append({"name": name, "rejected": True,
                          "error_type": type(error).__name__, "reason": str(error)})
        else:
            cases.append({"name": name, "rejected": False,
                          "error_type": None, "reason": None})
    rejected = sum(value["rejected"] for value in cases)
    return {"case_count": len(cases), "rejected_count": rejected,
            "all_invalid_cases_rejected": rejected == len(cases), "cases": cases}


def write_canonical(path: Path, events: list[dict]) -> dict:
    return write_events(path, canonicalize_events(events))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path,
                        help="Optional new directory for the two replay files")
    parser.add_argument("--report", type=Path,
                        help="Optional new path for the machine-readable report")
    args = parser.parse_args()
    events, stream = read_events(args.input)
    temporary = tempfile.TemporaryDirectory() if args.output_dir is None else None
    output_dir = Path(temporary.name) if temporary is not None else args.output_dir
    if args.output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=False)
    replay_a = output_dir / "replay-a.jsonl"
    replay_b = output_dir / "replay-b.jsonl"
    write_canonical(replay_a, events)
    write_canonical(replay_b, events)
    hash_a, hash_b = file_sha256(replay_a), file_sha256(replay_b)
    mapping = mapping_coverage(events)
    clock = clock_quality(events)
    completeness = field_completeness(events)
    negative = run_negative_matrix(events)
    warnings = []
    if not clock["resolution_floor_gate_passed"]:
        warnings.append("Historical observer clock evidence has a zero uncertainty floor")
    if mapping["session_counts"]["inferred"]:
        warnings.append("PID mapping is supported inference, not direct namespace ground truth")
    report = {
        "schema_version": "agentops-observation-quality-gate-v0.1",
        "source": str(args.input),
        "source_sha256": file_sha256(args.input),
        "stream": stream,
        "deterministic_replay": {
            "replay_count": 2,
            "sha256": [hash_a, hash_b],
            "byte_identical": replay_a.read_bytes() == replay_b.read_bytes(),
        },
        "mapping_coverage": mapping,
        "clock_quality": clock,
        "field_completeness": completeness,
        "negative_protocol_matrix": negative,
        "publication_component_gate": {
            "status": "READY_WITH_WARNINGS" if negative["all_invalid_cases_rejected"] else "NOT_READY",
            "blocking_implementation_failures": [] if negative["all_invalid_cases_rejected"] else [
                "One or more invalid protocol streams were accepted"
            ],
            "evidence_warnings": warnings,
        },
        "network_calls": 0,
        "code_provenance": {
            "application_events_v2.py": file_sha256(Path(__file__).with_name("application_events_v2.py")),
            "observation_quality_gate.py": file_sha256(Path(__file__)),
        },
        "environment": {
            "system": platform.system(),
            "python": platform.python_version(),
        },
    }
    if args.report is not None:
        if args.report.exists():
            raise FileExistsError(args.report)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if temporary is not None:
        temporary.cleanup()
    return 0 if negative["all_invalid_cases_rejected"] and hash_a == hash_b else 2


if __name__ == "__main__":
    raise SystemExit(main())
