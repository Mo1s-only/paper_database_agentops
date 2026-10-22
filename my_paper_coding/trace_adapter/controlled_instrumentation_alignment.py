#!/usr/bin/env python3
"""Emit a separate, provenance-bound relation profile for explicitly instrumented runs."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from align_candidates import ROOT, sha256, write_json, write_jsonl
from analyze_scenario_tool_id_bridge import analyze
from application_events import read_events


def run(run_dir: Path, app_path: Path, output: Path) -> dict:
    """Create a new controlled-instrumentation output directory; never replace one."""
    if output.exists():
        raise FileExistsError(f"Refusing to replace controlled instrumentation profile: {output}")
    plan_path = run_dir / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    bridge = plan.get("tool_id_bridge", {})
    if bridge.get("enabled") is not True or bridge.get("mode") != "controlled_hook_instrumentation":
        raise ValueError("Run plan does not explicitly enable controlled hook instrumentation")

    app_events, app_info = read_events(app_path)
    native_tools = {}
    for line_no, event in enumerate(app_events, 1):
        if event["event_type"] == "tool.start":
            native_tools[event["tool_call_id"]] = {
                "agent_id": event["agent_id"], "session_id": event["session_id"],
                "step_id": event["step_id"], "application_event_id": event["event_id"],
                "source_ref": f"{app_path.resolve().relative_to(ROOT).as_posix()}#line={line_no}",
            }

    audit = analyze(run_dir)
    source_hashes = audit.get("source_artifacts", {})
    if not source_hashes:
        raise ValueError("The runtime audit did not bind any raw source artifacts")
    source_paths = {}
    for name, expected_hash in source_hashes.items():
        path = (run_dir / name).resolve()
        if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
            raise ValueError(f"Runtime source is missing or escapes workspace: {name}")
        actual_hash = sha256(path)
        if actual_hash != expected_hash:
            raise ValueError(f"Runtime source changed while building profile: {name}")
        source_paths[name] = {"path": path.relative_to(ROOT.resolve()).as_posix(),
                              "sha256": actual_hash}

    decisions = []
    for link in audit.get("tool_links", []):
        ident = link["tool_call_id"]
        app = native_tools.get(ident)
        required = (
            app is not None
            and link.get("status") == "direct_instrumented_id_to_process_lineage"
            and link.get("agentsight_tool_id_exact_match") is True
            and link.get("hook_pretooluse_observed") is True
            and link.get("hook_tagged_bash") is True
            and link.get("hook_posttooluse_observed") is True
            and bool(link.get("ebpf_exact_id_carrier_source_refs"))
            and bool(link.get("ebpf_linked_scenario_child_execs"))
            and bool(link.get("agentsight_tool_source_ref"))
        )
        if required:
            status, reason = "accepted", "exact_tool_id_hook_marker_and_ebpf_pid_lineage"
        elif app is None:
            status, reason = "abstain", "native_application_tool_start_missing"
        else:
            status, reason = "abstain", "controlled_instrumentation_evidence_incomplete"
        evidence_refs = [app["source_ref"]] if app else []
        evidence_refs.extend(ref for ref in (
            link.get("native_source_ref"), link.get("hook_pre_source_ref"),
            link.get("hook_post_source_ref"), link.get("agentsight_tool_source_ref"),
            *(link.get("ebpf_exact_id_carrier_source_refs") or []),
            *(child.get("source_ref") for child in link.get("ebpf_linked_scenario_child_execs", [])),
        ) if ref)
        decisions.append({
            "relation_type": "controlled_instrumentation.tool_to_runtime_process_lineage",
            "profile": "controlled_instrumentation",
            "run_id": plan.get("run_id"), "tool_call_id": ident,
            "tool_name": link.get("tool_name"),
            "agent_id": app["agent_id"] if app else link.get("agent_id"),
            "session_id": app["session_id"] if app else None,
            "step_id": app["step_id"] if app else None,
            "status": status, "reason": reason,
            "hook_instrumented": bool(link.get("hook_pretooluse_observed")),
            "identity_basis": "hook_injected_shared_id_and_pid_lineage",
            "ebpf_carrier_pids": link.get("ebpf_exact_id_carrier_pids", []),
            "ebpf_linked_child_execs": link.get("ebpf_linked_scenario_child_execs", []),
            "evidence_refs": evidence_refs,
            "responsibility_claim": False,
            "ground_truth_used": False,
            "limitation": (
                "This relation exists only because the controlled PreToolUse hook injected the exact Claude tool ID "
                "into a tagged Bash wrapper observed by eBPF. It is not passive AgentSight identity and does not "
                "establish fault responsibility or causality."
            ),
        })

    # Include semantic tool starts absent from the runtime audit so missing capture is visible.
    audited_ids = {row["tool_call_id"] for row in decisions}
    for ident, app in native_tools.items():
        if ident not in audited_ids:
            decisions.append({
                "relation_type": "controlled_instrumentation.tool_to_runtime_process_lineage",
                "profile": "controlled_instrumentation", "run_id": plan.get("run_id"),
                "tool_call_id": ident, "tool_name": None,
                "agent_id": app["agent_id"], "session_id": app["session_id"],
                "step_id": app["step_id"], "status": "abstain", "reason": "runtime_audit_tool_id_missing",
                "hook_instrumented": False,
                "identity_basis": "hook_injected_shared_id_and_pid_lineage",
                "evidence_refs": [app["source_ref"]], "responsibility_claim": False,
                "ground_truth_used": False,
                "limitation": "No complete controlled hook/AgentSight/eBPF chain was found for this native tool ID.",
            })

    output.mkdir(parents=True)
    audit_path = output / "tool-id-process-audit.json"
    write_json(audit_path, audit)
    write_jsonl(output / "application-process-alignments.jsonl", decisions)
    counts = Counter(row["status"] for row in decisions)
    by_tool = {}
    for tool_name in sorted({row.get("tool_name") or "unknown" for row in decisions}):
        subset = [row for row in decisions if (row.get("tool_name") or "unknown") == tool_name]
        by_tool[tool_name] = {"total": len(subset), **dict(Counter(row["status"] for row in subset)),
                              "hook_instrumented": sum(row["hook_instrumented"] for row in subset)}
    instrumented = [row for row in decisions if row["hook_instrumented"]]
    summary = {
        "schema_version": "agentops-controlled-instrumentation-alignment-v0.1",
        "run_id": plan.get("run_id"), "profile": "controlled_instrumentation",
        "application_event_count": app_info["event_count"],
        "native_tool_starts": len(native_tools), "relation_count": len(decisions),
        "status_counts": dict(counts), "source_artifacts": source_paths,
        "by_tool_name": by_tool,
        "instrumented_tool_count": len(instrumented),
        "instrumented_acceptance_count": sum(row["status"] == "accepted" for row in instrumented),
        "application_events": {"path": app_path.resolve().relative_to(ROOT.resolve()).as_posix(),
                                "sha256": sha256(app_path)},
        "plan": {"path": plan_path.resolve().relative_to(ROOT.resolve()).as_posix(),
                 "sha256": sha256(plan_path)},
        "audit": {"path": audit_path.resolve().relative_to(ROOT.resolve()).as_posix(),
                  "sha256": sha256(audit_path)},
        "application_events_sha256": sha256(app_path), "plan_sha256": sha256(plan_path),
        "audit_sha256": sha256(audit_path),
        "claims": {"direct_hook_id_to_ebpf_lineage": counts["accepted"],
                   "passive_agentsight_tool_identity": False,
                   "responsibility_or_causality": False,
                   "ground_truth_used": False},
        "boundary": (
            "A relation is accepted only in this opt-in profile when the exact native tool ID is present in the "
            "hook, AgentSight tool_calls, an eBPF marker carrier, and a candidate child exec PID lineage. "
            "The generic process-and-tool profile is not modified and remains independently fail-closed."
        ),
    }
    write_json(output / "controlled-instrumentation-report.json", summary)
    return summary

