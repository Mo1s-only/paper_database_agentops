#!/usr/bin/env python3
"""Join explicit application tool steps with scoped system observations; never infer roots of failure."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from align_candidates import ROOT, field, load_evidence, locator, number, pid, sha256, write_json, write_jsonl
from application_events import integer, read_events, validate_stream


def join_application(events: list[dict], records: list[dict], scope: dict, app_source: str,
                     identity_mode: str = "process-and-tool") -> tuple[list, dict]:
    if identity_mode not in {"process-and-tool", "shared-tool-id", "session-and-tool"}:
        raise ValueError("Unknown identity mode")
    info = validate_stream(events)
    rows = [r for r in records if r.get("evidence_status") == "observed"
            and r.get("source", {}).get("role") == "raw_observation"
            and r.get("source", {}).get("path") == scope.get("source_path")]
    tools = [r for r in rows if r["record_type"] == "agentsight.tool_calls"]
    llms = [r for r in rows if r["record_type"] == "agentsight.llm_calls"]
    processes = [r for r in rows if r["record_type"] == "agentsight.process_nodes"]
    decisions = []
    for line, app in enumerate(events, 1):
        if app["event_type"] != "tool.start":
            continue
        refs = [f"{app_source}#line={line}"]
        result = {"application_event_id": app["event_id"], "run_id": app["run_id"],
                  "session_id": app["session_id"], "agent_id": app["agent_id"], "step_id": app["step_id"],
                  "tool_call_id": app["tool_call_id"], "status": "abstain", "reason": None,
                  "target_ref": None, "candidate_refs": [], "evidence_refs": refs,
                  "identity_source": "explicit_application_event", "confidence": None,
                  "responsibility_claim": False, "evidence_kind": info["evidence_kind"]}
        process = app["process"]
        if scope.get("schema_version") != "agentops-observation-scope-v0.1":
            result["reason"] = "missing_observation_scope"
        elif app["run_id"] != scope.get("run_id"):
            result["reason"] = "run_scope_conflict"
        elif info["evidence_kind"] != scope.get("evidence_kind"):
            result["reason"] = "evidence_kind_conflict"
        elif any(process[k] != scope.get(k) for k in ("host_id", "boot_id")):
            result["reason"] = "host_boot_or_namespace_conflict"
        elif identity_mode in {"shared-tool-id", "session-and-tool"}:
            candidates = [r for r in tools if field(r, "tool_call_id") == app["tool_call_id"]]
            result["candidate_refs"] = [locator(r) for r in candidates]
            result["process_alignment_status"] = "not_evaluated_in_shared_id_mode"
            result["clock_alignment_status"] = "not_evaluated_in_shared_id_mode"
            session_rows = [r for r in llms if field(r, "session_id") == app["session_id"]]
            session_pids = {pid(r) for r in session_rows if pid(r) is not None}
            if identity_mode == "session-and-tool" and not session_rows:
                result["reason"] = "application_session_not_observed"
            elif identity_mode == "session-and-tool" and len(session_pids) != 1:
                result.update(status="uncertain", reason="application_session_pid_not_unique")
            elif len(candidates) == 1 and (identity_mode == "shared-tool-id" or pid(candidates[0]) in session_pids):
                result.update(status="accepted", reason="unique_shared_native_tool_id_only",
                              target_ref=locator(candidates[0]), evidence_refs=refs + [locator(candidates[0])])
                if identity_mode == "session-and-tool":
                    result["reason"] = "shared_application_session_and_unique_tool_id"
                    result["evidence_refs"].extend(locator(r) for r in session_rows)
                    result["session_system_pid"] = next(iter(session_pids))
            elif len(candidates) == 1 and identity_mode == "session-and-tool":
                result.update(status="uncertain", reason="session_tool_pid_conflict")
            elif candidates:
                result.update(status="uncertain", reason="duplicate_system_tool_id")
            else:
                result["reason"] = "shared_tool_id_not_observed"
        elif process["pid_namespace"] != scope.get("pid_namespace"):
            result["reason"] = "host_boot_or_namespace_conflict"
        elif app["clock"]["domain"] != scope.get("clock_domain") or not integer(scope.get("uncertainty_ms")):
            result["reason"] = "incomparable_or_unbounded_clocks"
        else:
            candidates = [r for r in tools if field(r, "tool_call_id") == app["tool_call_id"]]
            result["candidate_refs"] = [locator(r) for r in candidates]
            if not candidates:
                result["reason"] = "shared_tool_id_not_observed"
            elif len(candidates) != 1:
                result.update(status="uncertain", reason="duplicate_system_tool_id")
            elif pid(candidates[0]) != process["pid"]:
                result.update(status="uncertain", reason="tool_pid_conflict")
            else:
                tool = candidates[0]
                budget = app["clock"]["uncertainty_ms"] + scope["uncertainty_ms"]
                matching = [p for p in processes if pid(p) == process["pid"]]
                # Unknown start/lifetime competitors cannot be safely discarded under PID reuse.
                possible = [p for p in matching if not number(field(p, "start_timestamp_ms"))
                            or abs(field(p, "start_timestamp_ms") - process["start_ms"]) <= budget]
                if len(possible) != 1:
                    result.update(status="uncertain" if possible else "abstain", reason="process_identity_not_unique")
                else:
                    p = possible[0]
                    start, end, t = field(p, "start_timestamp_ms"), field(p, "end_timestamp_ms"), tool.get("timestamp")
                    app_t = app["timestamp_ms"]
                    if not all(number(v) for v in (start, end, t)):
                        result.update(status="uncertain", reason="missing_process_or_tool_time")
                    elif not (start <= app_t - budget <= app_t + budget <= end and start <= t <= end):
                        result.update(status="uncertain", reason="time_interval_not_contained")
                    else:
                        result.update(status="accepted", reason="shared_tool_id_scoped_process_and_bounded_clock",
                                      target_ref=locator(tool), evidence_refs=refs + [locator(tool), locator(p)])
        decisions.append(result)
    # Two application identities cannot both own the same system event, even with a reused ID.
    owners = Counter(d["target_ref"] for d in decisions if d["status"] == "accepted")
    for d in decisions:
        if d["status"] == "accepted" and owners[d["target_ref"]] > 1:
            d.update(status="uncertain", reason="multiple_application_owners", target_ref=None)
    counts = Counter(d["status"] for d in decisions)
    return decisions, {**info, "tool_alignment_count": len(decisions), "status_counts": dict(counts),
                       "identity_mode": identity_mode,
                       "tool_identity_gate_passed": bool(decisions) and counts["accepted"] == len(decisions),
                       "scope": "tool.start events only; not all steps or causal responsibility",
                       "precision": None, "recall": None, "unified_trace_ready": False,
                       "responsibility_claim_made": False}


def run(manifest_path: Path, evidence_path: Path, app_path: Path, scope_path: Path, output: Path,
        identity_mode: str = "process-and-tool") -> dict:
    if output.exists():
        raise FileExistsError("Refusing to replace existing application alignment")
    manifest, records, audit = load_evidence(manifest_path, evidence_path)
    app_ref = app_path.resolve().relative_to(ROOT).as_posix()
    artifacts = {a["path"]: a for a in manifest["artifacts"]}
    artifact = artifacts.get(app_ref, {})
    if artifact.get("category") != "app_log" or artifact.get("sha256") != sha256(app_path):
        raise ValueError("Application event file is not a hash-verified app_log in manifest")
    events, info = read_events(app_path)
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    if manifest["run_id"] != info["run_id"]:
        raise ValueError("Manifest/application run mismatch")
    if scope.get("source_sha256") != audit["verified_sources"].get(scope.get("source_path")) or not scope.get("source_sha256"):
        raise ValueError("Observation scope is not bound to a hash-verified raw source")
    decisions, summary = join_application(events, records, scope, app_ref, identity_mode)
    summary["input_audit"] = {**audit, "application_sha256": sha256(app_path), "scope_sha256": sha256(scope_path)}
    output.mkdir(parents=True)
    write_jsonl(output / "application-alignments.jsonl", decisions)
    write_jsonl(output / "application-trace.jsonl", [
        {"run_id": e["run_id"], "session_id": e["session_id"], "agent_id": e["agent_id"],
         "step_id": e["step_id"], "tool_call_id": e["tool_call_id"], "event_type": e["event_type"],
         "timestamp_ms": e["timestamp_ms"], "evidence_kind": e["evidence_kind"],
         "identity_status": "explicit_application_identity", "evidence_refs": [f"{app_ref}#line={i}"],
         "responsibility_claim": False} for i, e in enumerate(events, 1)])
    write_json(output / "application-alignment-report.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "evidence", "app-events", "scope", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--identity-mode", choices=("process-and-tool", "shared-tool-id", "session-and-tool"), default="process-and-tool")
    args = parser.parse_args()
    try:
        summary = run(args.manifest, args.evidence, args.app_events, args.scope, args.output, args.identity_mode)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Application input gate failed: {error}\n")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["tool_identity_gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
