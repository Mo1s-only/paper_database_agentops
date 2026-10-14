#!/usr/bin/env python3
"""Build and replay a queryable evidence package without making attribution claims."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from application_events_v2 import read_events, validate_stream
from model_invocation_context import read_contexts, validate_contexts


VERSION = "agentops-pre-attribution-evidence-v0.1"
ALLOWED_SELECTOR_FIELDS = {
    "run_id", "event_id", "session_id", "agent_id", "event_type", "step_id", "tool_call_id",
    "process.host_id", "process.boot_id", "process.local_pid",
    "process.local_pid_namespace", "process.observer_pid",
    "process.observer_pid_namespace", "process.mapping_status",
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nested_value(event: dict, field: str) -> Any:
    value: Any = event
    for part in field.split("."):
        value = value[part]
    return value


def execute_query(events: list[dict], selector: dict) -> list[dict]:
    if not isinstance(selector, dict) or not selector:
        raise ValueError("A query selector must contain at least one exact-match field")
    unknown = set(selector) - ALLOWED_SELECTOR_FIELDS
    if unknown:
        raise ValueError(f"Unsupported selector fields: {sorted(unknown)}")
    return [event for event in events if all(
        nested_value(event, field) == expected for field, expected in selector.items())]


def make_query(events: list[dict], purpose: str, selector: dict) -> dict:
    selected = execute_query(events, selector)
    definition = {"operation": "select_events_exact", "selector": selector}
    return {
        "query_id": "q-" + digest({"purpose": purpose, **definition})[:16],
        "purpose": purpose,
        **definition,
        "result_count": len(selected),
        "result_event_ids": [event["event_id"] for event in selected],
        "result_sha256": digest(selected),
    }


def mapping_evidence_status(status: str) -> str:
    return {"accepted": "direct", "inferred": "inferred", "abstain": "abstain"}[status]


def build_package(events: list[dict], gate: dict,
                  invocation_contexts: list[dict] | None = None) -> dict:
    stream = validate_stream(events)
    if not gate.get("ready_modes", {}).get("identity_and_tool_graph", False):
        raise ValueError("Identity and tool graph gate is not ready")

    bounded_time = bool(gate["ready_modes"].get("bounded_temporal_ordering", False))
    queries: list[dict] = []
    query_by_key: dict[tuple, dict] = {}

    def add_query(purpose: str, selector: dict) -> dict:
        key = (purpose, canonical_bytes(selector))
        if key not in query_by_key:
            value = make_query(events, purpose, selector)
            query_by_key[key] = value
            queries.append(value)
        return query_by_key[key]

    relations = []
    for session_id in sorted({event["session_id"] for event in events}):
        session_events = [event for event in events if event["session_id"] == session_id]
        session_query = add_query("replay complete session lifecycle", {"session_id": session_id})
        process = session_events[0]["process"]
        process_query = add_query(
            "replay session events with the observed process mapping",
            {"session_id": session_id, "process.mapping_status": process["mapping_status"]},
        )
        relations.append({
            "relation_id": "r-" + digest([session_id, "observed_in_process"])[:16],
            "relation_type": "session_observed_in_process",
            "source": {"kind": "session", "id": session_id},
            "target": {
                "kind": "process_view",
                "id": f"{process['host_id']}:{process['boot_id']}:{process['local_pid_namespace']}:{process['local_pid']}",
            },
            "evidence_status": mapping_evidence_status(process["mapping_status"]),
            "evidence_event_ids": process_query["result_event_ids"],
            "query_ids": [process_query["query_id"]],
            "time_relation": "not_applicable",
            "causal_claim": False,
            "responsibility_claim": False,
        })

        for step_id in sorted({event["step_id"] for event in session_events if event["step_id"]}):
            step_query = add_query("replay events for one framework step",
                                   {"session_id": session_id, "step_id": step_id})
            relations.append({
                "relation_id": "r-" + digest([session_id, step_id, "contains_step"])[:16],
                "relation_type": "session_contains_step",
                "source": {"kind": "session", "id": session_id},
                "target": {"kind": "step", "id": step_id},
                "evidence_status": "direct",
                "evidence_event_ids": step_query["result_event_ids"],
                "query_ids": [session_query["query_id"], step_query["query_id"]],
                "time_relation": "sequence_only" if not bounded_time else "bounded_application_clock",
                "causal_claim": False,
                "responsibility_claim": False,
            })

            for tool_id in sorted({event["tool_call_id"] for event in session_events
                                   if event["step_id"] == step_id and event["tool_call_id"]}):
                tool_query = add_query("replay one framework tool lifecycle", {
                    "session_id": session_id, "step_id": step_id, "tool_call_id": tool_id,
                })
                tool_events = execute_query(events, tool_query["selector"])
                kinds = {event["event_type"] for event in tool_events}
                closed = kinds == {"tool.start", "tool.end"}
                relations.append({
                    "relation_id": "r-" + digest([session_id, step_id, tool_id,
                                                    "invokes_tool"])[:16],
                    "relation_type": "step_invokes_tool",
                    "source": {"kind": "step", "id": step_id},
                    "target": {"kind": "tool_call", "id": tool_id},
                    "evidence_status": "direct" if closed else "abstain",
                    "evidence_event_ids": tool_query["result_event_ids"],
                    "query_ids": [tool_query["query_id"]],
                    "time_relation": "sequence_only_unbounded" if not bounded_time else "bounded_application_clock",
                    "lifecycle_closed": closed,
                    "causal_claim": False,
                    "responsibility_claim": False,
                })

    observer_events = [event for event in events
                       if event["clock"]["observer_raw_boot_ns"] is not None]
    observer_event_ids = [event["event_id"] for event in observer_events]
    for observer_event in observer_events:
        add_query("replay one event containing observer-side clock evidence",
                  {"event_id": observer_event["event_id"]})
    all_processes = {(
        event["process"]["host_id"], event["process"]["boot_id"],
        event["process"]["local_pid_namespace"], event["process"]["local_pid"],
        event["process"]["mapping_status"],
    ) for event in events}

    mirror_required = [
        "model_id", "model_version", "sampling_temperature", "sampling_top_p",
        "system_prompt_sha256", "tool_schema_sha256", "request_id",
        "response_id", "pairing_method", "pairing_evidence",
    ]
    invocation_contexts = invocation_contexts or []
    context_summary = validate_contexts(
        invocation_contexts, stream["run_id"],
        {event["session_id"] for event in events},
    )
    mirror_ready = context_summary["all_sessions_covered"]
    package = {
        "schema_version": VERSION,
        "stream": stream,
        "canonical_event_stream_sha256": digest(events),
        "design_sources": {
            "RCACopilot": "composable evidence channels",
            "OpenRCA": "programmatic exact-match telemetry queries",
            "Watson": "explicit readiness check before post-hoc reasoning reconstruction",
            "OpenRCA_2.0": "claim-level evidence receipts and replay verification",
        },
        "collection_handlers": [
            {
                "handler_id": "application_lifecycle_v0.2",
                "channel": "framework_lifecycle",
                "status": "available",
                "evidence_kind": stream["evidence_kind"],
                "event_count": stream["event_count"],
            },
            {
                "handler_id": "process_mapping_v0.2",
                "channel": "process_identity",
                "status": "available_with_inference" if any(p[-1] == "inferred" for p in all_processes)
                          else "available",
                "process_view_count": len(all_processes),
            },
            {
                "handler_id": "observer_clock_v0.2",
                "channel": "observer_clock",
                "status": "available_without_strict_bound" if not bounded_time else "available",
                "observer_clock_event_count": len(observer_event_ids),
            },
            {
                "handler_id": "model_invocation_context_v0.1",
                "channel": "reasoning_reconstruction_inputs",
                "status": "available" if mirror_ready else "unavailable",
                "context_count": context_summary["context_count"],
                "missing_fields": [] if mirror_ready else mirror_required,
            },
        ],
        "queries": queries,
        "observed_relations": relations,
        "mirror_readiness": {
            "status": "READY" if mirror_ready else "NOT_READY",
            "method": "watson_style_post_hoc_reconstruction",
            "missing_fields": [] if mirror_ready else mirror_required,
            "context_summary": context_summary,
            "default_values_invented": False,
            "reconstruction_attempted": False,
        },
        "readiness": {
            "queryable_evidence_package": True,
            "identity_and_tool_relations": bool(relations),
            "bounded_temporal_relations": bounded_time,
            "reasoning_reconstruction": mirror_ready,
            "causal_attribution": False,
        },
        "claims": {
            "root_cause_generated": False,
            "responsibility_generated": False,
            "causal_path_generated": False,
        },
        "boundaries": [
            "Observed relations are structural evidence, not causal edges.",
            "Sequence order is not promoted to a strict cross-layer time order when the clock gate is closed.",
            "Inferred PID mapping remains inferred until direct namespace ground truth is observed.",
            "Watson-style reconstruction is disabled until all required invocation context is captured.",
        ],
        "network_calls": 0,
    }
    return package


def verify_package(events: list[dict], package: dict) -> dict:
    validate_stream(events)
    failures = []
    if package.get("schema_version") != VERSION:
        failures.append({"reason": "unsupported evidence package schema"})
    if package.get("canonical_event_stream_sha256") != digest(events):
        failures.append({"reason": "canonical event stream hash differs"})
    for query in package.get("queries", []):
        try:
            selected = execute_query(events, query["selector"])
        except (KeyError, TypeError, ValueError) as exc:
            failures.append({"query_id": query.get("query_id"), "reason": str(exc)})
            continue
        actual_ids = [event["event_id"] for event in selected]
        if query.get("operation") != "select_events_exact":
            failures.append({"query_id": query.get("query_id"), "reason": "unsupported operation"})
        if actual_ids != query.get("result_event_ids"):
            failures.append({"query_id": query.get("query_id"), "reason": "event IDs differ"})
        if digest(selected) != query.get("result_sha256"):
            failures.append({"query_id": query.get("query_id"), "reason": "result hash differs"})
    query_list = package.get("queries", [])
    query_ids = {query["query_id"] for query in query_list}
    query_results = {query["query_id"]: set(query.get("result_event_ids", []))
                     for query in query_list}
    relation_list = package.get("observed_relations", [])
    relation_receipts_complete = all(
        relation.get("evidence_event_ids") and relation.get("query_ids") and
        set(relation["query_ids"]).issubset(query_ids) and
        set(relation["evidence_event_ids"]).issubset(set().union(*(
            query_results[query_id] for query_id in relation["query_ids"]))) and
        relation.get("causal_claim") is False and relation.get("responsibility_claim") is False
        for relation in relation_list
    )
    identifiers_unique = (
        len(query_ids) == len(query_list) and
        len({relation["relation_id"] for relation in relation_list}) == len(relation_list)
    )
    forbidden_claims_absent = package.get("claims") == {
        "root_cause_generated": False,
        "responsibility_generated": False,
        "causal_path_generated": False,
    }
    if not relation_receipts_complete:
        failures.append({"reason": "relation receipts are incomplete or contain a forbidden claim"})
    if not identifiers_unique:
        failures.append({"reason": "query or relation identifiers are not unique"})
    if not forbidden_claims_absent:
        failures.append({"reason": "forbidden attribution claim present"})
    return {
        "schema_version": "agentops-pre-attribution-evidence-verification-v0.1",
        "query_count": len(package.get("queries", [])),
        "relation_count": len(package.get("observed_relations", [])),
        "all_queries_replayed": not any("query_id" in item for item in failures),
        "relation_receipts_complete": relation_receipts_complete,
        "identifiers_unique": identifiers_unique,
        "forbidden_claims_absent": forbidden_claims_absent,
        "passed": not failures,
        "failures": failures,
        "network_calls": 0,
    }


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_output(path: Path, value: dict, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "x"
    with path.open(mode, encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--events", type=Path, required=True)
    build.add_argument("--gate", type=Path, required=True)
    build.add_argument("--invocation-context", type=Path)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--force", action="store_true")
    verify = subparsers.add_parser("verify")
    verify.add_argument("--events", type=Path, required=True)
    verify.add_argument("--package", type=Path, required=True)
    verify.add_argument("--output", type=Path, required=True)
    verify.add_argument("--force", action="store_true")
    args = parser.parse_args()

    events, _ = read_events(args.events)
    if args.command == "build":
        contexts = read_contexts(args.invocation_context) if args.invocation_context else []
        package = build_package(events, load_json(args.gate), contexts)
        package["input_sha256"] = {
            "events": file_sha256(args.events),
            "pre_attribution_gate": file_sha256(args.gate),
        }
        if args.invocation_context:
            package["input_sha256"]["invocation_context"] = file_sha256(args.invocation_context)
        write_output(args.output, package, args.force)
        print(json.dumps(package, ensure_ascii=False))
        return 0
    result = verify_package(events, load_json(args.package))
    result["input_sha256"] = {
        "events": file_sha256(args.events),
        "evidence_package": file_sha256(args.package),
    }
    write_output(args.output, result, args.force)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
