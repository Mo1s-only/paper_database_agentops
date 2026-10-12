#!/usr/bin/env python3
"""Combine observation evidence gates before any attribution method may consume a trace."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(quality: dict, analysis: dict, namespace_matrix: dict) -> dict:
    lifecycle = (quality["stream"]["all_sessions_closed"] and
                 quality["field_completeness"]["all_required_lifecycle_kinds_present"])
    fields = quality["field_completeness"]["overall_rate"] == 1.0
    replay = quality["deterministic_replay"]["byte_identical"]
    rejection = quality["negative_protocol_matrix"]["all_invalid_cases_rejected"]
    native_tools = analysis["framework_lifecycle"]["tool_use"]
    matched_tools = analysis["agentsight_tool_match_count"]
    capture_complete = native_tools > 0 and native_tools == matched_tools and analysis["native_tool_closed"]
    mapping_policy = namespace_matrix["acceptance_passed"]
    real_statuses = quality["mapping_coverage"]["session_counts"]
    real_mapping_supported = real_statuses["accepted"] + real_statuses["inferred"] > 0
    clock_formula = (analysis["agentsight_tool_epoch_formula_verified"] and
                     analysis["applied_clock_correction_ns"] == 0)
    resolution_floor = quality["clock_quality"]["resolution_floor_gate_passed"]
    identity_graph_ready = all((lifecycle, fields, replay, rejection, capture_complete,
                                mapping_policy, real_mapping_supported, clock_formula))
    bounded_temporal_ordering_ready = identity_graph_ready and resolution_floor
    warnings = []
    if real_statuses["inferred"]:
        warnings.append("Real PID mapping is supported inference rather than direct NSpid truth")
    if not resolution_floor:
        warnings.append("Historical observer clock uncertainty is unbounded for strict timing claims")
    status = "READY" if bounded_temporal_ordering_ready else (
        "READY_WITH_WARNINGS" if identity_graph_ready else "NOT_READY")
    return {
        "status": status,
        "checks": {
            "lifecycle_closed": lifecycle,
            "required_fields_complete": fields,
            "deterministic_replay": replay,
            "invalid_streams_rejected": rejection,
            "native_tool_capture_complete": capture_complete,
            "pid_mapping_policy_passed": mapping_policy,
            "real_pid_mapping_supported": real_mapping_supported,
            "observer_clock_formula_verified": clock_formula,
            "observer_clock_resolution_floor_verified_in_source_event": resolution_floor,
        },
        "tool_capture": {
            "native_tool_use_count": native_tools,
            "agentsight_match_count": matched_tools,
            "complete": capture_complete,
        },
        "ready_modes": {
            "identity_and_tool_graph": identity_graph_ready,
            "bounded_temporal_ordering": bounded_temporal_ordering_ready,
            "responsibility_or_root_cause": False,
        },
        "warnings": warnings,
        "responsibility_claim_made": False,
        "network_calls": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quality-report", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--namespace-matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    quality, analysis, matrix = map(load, (
        args.quality_report, args.analysis, args.namespace_matrix))
    result = {
        "schema_version": "agentops-pre-attribution-gate-v0.1",
        **evaluate(quality, analysis, matrix),
        "input_sha256": {
            str(args.quality_report): sha256(args.quality_report),
            str(args.analysis): sha256(args.analysis),
            str(args.namespace_matrix): sha256(args.namespace_matrix),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] != "NOT_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
