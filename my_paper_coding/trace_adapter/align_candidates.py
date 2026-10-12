#!/usr/bin/env python3
"""Offline, provenance-first associations. Never infer responsibility or agent IDs."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = {"raw_observation", "app_log"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, values: list[dict]) -> None:
    path.write_text("".join(json.dumps(v, ensure_ascii=False) + "\n" for v in values), encoding="utf-8")


def locator(record: dict) -> str:
    source = record["source"]
    if "table" in source and source.get("row") is not None:
        return f'{source["path"]}#{source["table"]}/{source["row"]}'
    if source.get("line") is not None:
        return f'{source["path"]}#line={source["line"]}'
    raise ValueError("Evidence requires a table/row or line locator")


def number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def load_evidence(manifest_path: Path, evidence_path: Path, root: Path = ROOT) -> tuple[dict, list, dict]:
    """Read only observed, allowlisted inputs; never open validator/derived artifacts."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = {a["path"]: a for a in manifest["artifacts"]}
    verified, records, excluded = {}, [], Counter()
    seen = set()
    for line_no, line in enumerate(evidence_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        event = json.loads(line)  # Malformed input must fail, not silently disappear.
        if not isinstance(event, dict):
            raise ValueError(f"Non-object input at line {line_no}")
        source = event.get("source", {})
        artifact = artifacts.get(source.get("path"))
        if (event.get("evidence_status") != "observed" or source.get("role") not in ALLOWED
                or not artifact or artifact.get("category") != source.get("role")):
            excluded["not_observed_or_not_allowlisted"] += 1
            continue
        path = (root / source["path"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Source escapes repository")
        if source["path"] not in verified:
            actual = sha256(path)
            if actual != artifact.get("sha256"):
                raise ValueError(f"Source hash mismatch: {source['path']}")
            verified[source["path"]] = actual
        ref = locator(event)
        if ref in seen:
            raise ValueError(f"Duplicate source locator: {ref}")
        seen.add(ref)
        records.append(event)
    return manifest, records, {
        "manifest_sha256": sha256(manifest_path), "evidence_sha256": sha256(evidence_path),
        "verified_sources": verified, "excluded_records": dict(excluded),
        "validator_artifacts_read": False, "derived_artifacts_read": False,
        "boundary": "Hashes freeze local inputs; normalized field extraction is not independently certified.",
    }


def field(record: dict, key: str) -> Any:
    value = record.get(key)
    return value if value is not None else record.get("fields", {}).get(key)


def pid(record: dict) -> Any:
    return field(record, "pid") if field(record, "pid") is not None else field(record, "related_pid")


def lifetime(process: dict, timestamp: Any) -> str:
    start = field(process, "start_timestamp_ms")
    end = field(process, "end_timestamp_ms")
    if not number(timestamp) or not number(start) or not number(end):
        return "unknown_lifetime"
    if start > end:
        return "invalid_lifetime"
    return "within_lifetime" if start <= timestamp <= end else "outside_lifetime"


def tool_ids(record: dict) -> set[str]:
    """Only structured tool blocks, never free-text substring or event-ID prefix guessing."""
    found = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("type") in {"tool_use", "function_call"}:
                ident = value.get("id") or value.get("call_id")
                if isinstance(ident, str) and ident:
                    found.add(ident)
            for key, child in value.items():
                if key in {"input", "arguments", "text", "text_content"}:
                    continue  # Tool arguments and prose are not tool-call declarations.
                if key == "json_content" and isinstance(child, str):
                    try:
                        visit(json.loads(child))
                    except json.JSONDecodeError:
                        pass
                elif isinstance(child, (dict, list)):
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    body = field(record, "response_body_json")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            body = None
    visit(body)
    return found


def align(records: list[dict], run_id: str) -> tuple[list, list, dict]:
    # Defense in depth when called directly by tests or other Python code.
    records = [r for r in records if r.get("evidence_status") == "observed"
               and r.get("source", {}).get("role") in ALLOWED]
    processes = [r for r in records if r["record_type"] == "agentsight.process_nodes"]
    llms = [r for r in records if r["record_type"] == "agentsight.llm_calls"]
    decisions = []

    def emit(kind: str, event: dict, options: list[tuple[dict, str]], accept: bool, reason: str) -> None:
        status = "accepted" if accept and len(options) == 1 else "uncertain" if options else "abstain"
        decisions.append({
            "association_id": f"assoc-{len(decisions) + 1:05d}", "run_id": run_id,
            "relation": kind, "source_ref": locator(event), "status": status,
            "reason": reason, "confidence": None,
            "confidence_semantics": "uncalibrated; status is rule acceptance, not truth probability",
            "candidates": [{"target_ref": locator(target), "basis": basis,
                            "evidence_refs": [locator(event), locator(target)]} for target, basis in options],
            "responsibility_claim": False,
        })

    for event in records:
        kind = event["record_type"]
        if kind in {"agentsight.tool_calls", "agentsight.llm_calls", "agentsight.audit_events"}:
            event_pid = pid(event)
            matching = [p for p in processes if event_pid is not None and pid(p) == event_pid]
            options = [(p, lifetime(p, event.get("timestamp"))) for p in matching]
            compatible = [(p, basis) for p, basis in options if basis not in {"outside_lifetime", "invalid_lifetime"}]
            accepted = len(compatible) == 1 and compatible[0][1] == "within_lifetime"
            reason = ("unique_pid_and_bounded_lifetime" if accepted else "ambiguous_or_missing_lifetime"
                      if compatible else "pid_not_observed" if not matching else "timestamp_conflict")
            # Keep rejected candidates for auditing even when all violate the time constraint.
            if not compatible:
                emit(kind.removeprefix("agentsight.") + "_process", event, [], False, reason)
                decisions[-1]["rejected_candidates"] = [
                    {"target_ref": locator(p), "reason": basis} for p, basis in options]
            else:
                emit(kind.removeprefix("agentsight.") + "_process", event, compatible, accepted, reason)
        if kind == "agentsight.process_nodes":
            parent_pid = field(event, "ppid")
            parents = [(p, lifetime(p, field(event, "start_timestamp_ms"))) for p in processes
                       if parent_pid is not None and pid(p) == parent_pid and locator(p) != locator(event)]
            parents = [(p, basis) for p, basis in parents if basis not in {"outside_lifetime", "invalid_lifetime"}]
            emit("process_parent", event, parents,
                 len(parents) == 1 and parents[0][1] == "within_lifetime", "ppid_and_lifetime")
        if kind == "agentsight.tool_calls":
            ident = field(event, "tool_call_id")
            exact = [(r, "structured_tool_call_id") for r in llms if ident and ident in tool_ids(r)]
            conflicts = any(pid(event) is not None and pid(r) is not None and pid(event) != pid(r)
                            for r, _ in exact)
            if exact:
                emit("tool_llm", event, exact, not conflicts,
                     "explicit_id_pid_conflict" if conflicts else "structured_tool_call_id")
            else:
                temporal = [(r, "same_pid_same_timestamp_only") for r in llms
                            if pid(event) is not None and pid(r) == pid(event)
                            and number(event.get("timestamp")) and r.get("timestamp") == event["timestamp"]]
                emit("tool_llm", event, temporal, False, "no_shared_structured_tool_id")
        if kind == "application.result":
            # AgentSight session_id belongs to the capture, not the application's namespace.
            emit("application_session_alignment", event, [], False,
                 "final_result_has_no_shared_request_tool_or_process_identity")

    trace = []
    for event in records:
        trace.append({
            "schema_version": "trace-adapter-draft-v0.1", "run_id": run_id,
            "trace_record_id": hashlib.sha256(locator(event).encode()).hexdigest()[:20],
            "record_type": event["record_type"], "observed_event_id": event.get("event_id"),
            "timestamp": event.get("timestamp"), "pid": pid(event),
            "tool_call_id": field(event, "tool_call_id"),
            "agent_id": None, "step_id": None, "identity_status": "unknown",
            "evidence_refs": [locator(event)],
            "association_ids": [d["association_id"] for d in decisions if d["source_ref"] == locator(event)],
            "responsibility_claim": False,
        })
    by_relation = {}
    for relation in sorted({d["relation"] for d in decisions}):
        subset = [d for d in decisions if d["relation"] == relation]
        counts = Counter(d["status"] for d in subset)
        by_relation[relation] = {"total": len(subset), **dict(counts),
                                 "accepted_coverage": counts["accepted"] / len(subset)}
    summary = {
        "run_id": run_id, "observed_records": len(records), "association_decisions": len(decisions),
        "status_counts": dict(Counter(d["status"] for d in decisions)), "by_relation": by_relation,
        "precision": None, "recall": None, "independent_alignment_labels_available": False,
        "metrics_boundary": "Coverage counts rule acceptance; precision/recall require independent labels.",
        "unified_trace_ready": False, "draft_available": True, "responsibility_claim_made": False,
        "next_capture_requirements": ["full application step/tool JSONL", "agent/session/process mapping",
                                      "shared request/tool IDs", "clock source and uncertainty"],
    }
    return decisions, trace, summary


def run(manifest_path: Path, evidence_path: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {output}")
    manifest, records, audit = load_evidence(manifest_path, evidence_path)
    decisions, trace, summary = align(records, manifest["run_id"])
    summary["input_audit"] = audit
    output.mkdir(parents=True)
    write_jsonl(output / "candidate-alignments.jsonl", decisions)
    write_jsonl(output / "unified-trace-draft.jsonl", trace)
    write_json(output / "alignment-report.json", summary)
    write_json(output / "provenance-graph.json", {
        "semantics": "observational associations, not causal or responsibility edges",
        "nodes": [{"id": locator(r), "record_type": r["record_type"]} for r in records],
        "edges": [{"source": d["source_ref"], "target": c["target_ref"], "relation": d["relation"],
                   "status": d["status"], "evidence_refs": c["evidence_refs"]}
                  for d in decisions for c in d["candidates"]],
    })
    write_jsonl(output / "alignment-review-template.jsonl", [
        {"association_id": d["association_id"], "source_ref": d["source_ref"],
         "candidate_refs": [c["target_ref"] for c in d["candidates"]],
         "review_status": "AUTHOR_INPUT_NEEDED", "verified_target_ref": None,
         "reviewer": None, "evidence_basis": None} for d in decisions])
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New directory; existing output is never replaced")
    args = parser.parse_args()
    try:
        summary = run(args.manifest, args.evidence, args.output)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Input/output gate failed: {error}\n")
    print(json.dumps({k: summary[k] for k in ("run_id", "observed_records", "status_counts", "unified_trace_ready")}, ensure_ascii=False))
    return 0  # Draft generation success, explicitly not alignment validation success.


if __name__ == "__main__":
    raise SystemExit(main())
