#!/usr/bin/env python3
"""Read a tiny, pinned public-dataset subset into a labels-only compatibility bundle.

This is not a runtime trace importer: public annotations remain labels/context and
are deliberately kept separate from Claude/AgentSight/eBPF observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from align_candidates import ROOT, write_json, write_jsonl


DATASETS = ROOT / "Reference paper" / "datasets"
DEFAULT_OUTPUT = ROOT / "lab" / "experiment" / "public_dataset_generalization_20261022"
SELECTION = [
    {"dataset": "AgentTrace", "family": "causal_graph", "path": "shared_data/AgentTrace_ICLR2026_data/traces/cod_034b23_trace.json"},
    {"dataset": "WhoAndWhen", "family": "agent_step_attribution", "split": "Algorithm-Generated", "path": "shared_data/WhoAndWhen_184/Algorithm-Generated/99.json"},
    {"dataset": "WhoAndWhen", "family": "agent_step_attribution", "split": "Hand-Crafted", "path": "shared_data/WhoAndWhen_184/Hand-Crafted/9.json"},
    {"dataset": "TRAIL", "family": "span_multi_error", "split": "GAIA", "path": "shared_data/TRAIL_benchmarking_148_traces.zip::benchmarking/processed_annotations_gaia/0035f455b3ff2295167a844f04d85d34.json"},
    {"dataset": "TRAIL", "family": "span_multi_error", "split": "SWE-bench", "path": "shared_data/TRAIL_benchmarking_148_traces.zip::benchmarking/processed_annotations_swe_bench/0e6f7928953ab5a568bae640ce915cc3.json"},
]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def flatten_span_ids(trace: dict) -> set[str]:
    span_ids: set[str] = set()
    pending = list(trace.get("spans", []))
    while pending:
        span = pending.pop()
        if span.get("span_id"):
            span_ids.add(str(span["span_id"]))
        pending.extend(span.get("child_spans", []))
    return span_ids


def load_source(relative: str) -> tuple[dict, dict]:
    spec = next(item for item in SELECTION if item["path"] == relative)
    source_path, member = (relative.split("::", 1) if "::" in relative else (relative, None))
    path = (DATASETS / source_path).resolve()
    if not path.is_relative_to(DATASETS.resolve()) or not path.is_file():
        raise ValueError(f"Missing or out-of-scope dataset input: {relative}")
    source_bytes = path.read_bytes()
    if member:
        with zipfile.ZipFile(path) as archive:
            raw = archive.read(member)
    else:
        raw = source_bytes
    value = json.loads(raw)
    common = {
        "dataset": spec["dataset"], "family": spec["family"], "split": spec.get("split"),
        "source_ref": f"Reference paper/datasets/{relative}",
        "source_artifact_sha256": sha256_bytes(source_bytes),
        "selected_record_sha256": sha256_bytes(raw),
        "evidence_role": "public_dataset_annotation_or_trace_not_runtime_observation",
    }
    if spec["dataset"] == "AgentTrace":
        trace = json.loads(value["trace_json"])
        nodes = trace.get("nodes", [])
        node_ids = {node.get("id") for node in nodes}
        path_ids = value.get("causal_path", [])
        if value.get("root_cause_node_id") not in node_ids or value.get("error_node_id") not in node_ids:
            raise ValueError("AgentTrace root/error label does not resolve to a trace node")
        if not set(path_ids).issubset(node_ids):
            raise ValueError("AgentTrace causal path contains unknown node IDs")
        record = {
            **common, "sample_id": value["scenario_id"],
            "structure": {"node_count": len(nodes), "edge_count": len(trace.get("edges", [])),
                          "domains": sorted({node.get("metadata", {}).get("domain") for node in nodes
                                             if node.get("metadata", {}).get("domain")})},
            "gold_labels": {"root_cause_node_id": value.get("root_cause_node_id"),
                            "error_node_id": value.get("error_node_id"),
                            "causal_path_node_ids": path_ids,
                            "error_occurred": value.get("error_occurred")},
            "available_identity_fields": {"agent_id": any(node.get("agent_id") for node in nodes),
                                           "step_id": any(node.get("data", {}).get("step") is not None for node in nodes),
                                           "tool_call_id": any(node.get("data", {}).get("tool_call_id") for node in nodes)},
        }
    elif spec["dataset"] == "WhoAndWhen":
        history = value.get("history", [])
        if not history or not value.get("mistake_agent") or value.get("mistake_step") is None:
            raise ValueError("WhoAndWhen selected record lacks history or attribution labels")
        record = {
            **common, "sample_id": value.get("question_ID"),
            "structure": {"history_turn_count": len(history),
                          "roles": sorted({turn.get("role", "unknown") for turn in history}),
                          "level": value.get("level")},
            "gold_labels": {"mistake_agent": value.get("mistake_agent"),
                            "mistake_step": value.get("mistake_step"),
                            "mistake_reason": value.get("mistake_reason"),
                            "ground_truth": value.get("ground_truth")},
            "available_identity_fields": {"agent_id": True, "step_id": True,
                                           "tool_call_id": False},
        }
    else:
        errors = value.get("errors", [])
        if not errors or any(not all(error.get(key) is not None for key in
                                     ("category", "location", "evidence", "description"))
                             for error in errors):
            raise ValueError("TRAIL selected record lacks structured span error annotations")
        sample_id = member.rsplit("/", 1)[-1].removesuffix(".json")
        trace_family = "GAIA" if spec["split"] == "GAIA" else "SWE Bench"
        trace_member = f"benchmarking/data/{trace_family}/{sample_id}.json"
        with zipfile.ZipFile(path) as archive:
            trace_raw = archive.read(trace_member)
        trace = json.loads(trace_raw)
        span_ids = flatten_span_ids(trace)
        matched_locations = [error["location"] for error in errors
                             if str(error["location"]) in span_ids]
        record = {
            **common, "sample_id": sample_id,
            "structure": {"error_count": len(errors),
                          "error_categories": sorted({error["category"] for error in errors})},
            "gold_labels": {"errors": [{"category": error["category"], "location": error["location"],
                                         "impact": error.get("impact"), "evidence": error["evidence"]}
                                        for error in errors]},
            "available_identity_fields": {"agent_id": False, "step_id": False,
                                           "tool_call_id": False},
            "public_trace_join": {
                "trace_member": trace_member,
                "trace_id": trace.get("trace_id"),
                "trace_record_sha256": sha256_bytes(trace_raw),
                "span_count": len(span_ids),
                "annotation_location_match_count": len(matched_locations),
                "annotation_location_count": len(errors),
                "all_annotations_resolve_to_span_id": len(matched_locations) == len(errors),
                "evidence_role": "historical_public_semantic_trace_not_current_ebpf_observation",
            },
        }
    record["runtime_evidence"] = {
        "claude_tool_ids": None, "agentsight_tool_ids": None,
        "process_events": None, "ebpf_pid_lineage": None,
        "status": "not_present_in_selected_public_artifact",
    }
    return record, {"path": source_path, "sha256": common["source_artifact_sha256"]}


def prepare(output: Path = DEFAULT_OUTPUT) -> dict:
    if output.exists():
        raise FileExistsError(f"Refusing to replace existing subset output: {output}")
    records, sources = [], {}
    for spec in SELECTION:
        record, source = load_source(spec["path"])
        records.append(record)
        sources[source["path"]] = source
    output.mkdir(parents=True)
    write_jsonl(output / "selected-cases.jsonl", records)
    report = {
        "schema_version": "agentops-public-dataset-subset-v0.1",
        "selected_dataset_families": sorted({row["dataset"] for row in records}),
        "selected_case_count": len(records), "cases_by_dataset": {},
        "sources": list(sources.values()),
        "input_policy": "Read-only source datasets; no API calls; labels never enter runtime-evidence inputs.",
        "what_this_validates": ["heterogeneous public annotation parsing", "label provenance and schema capability inventory",
                                 "TRAIL annotation-location to historical trace-span-ID joins"],
        "what_this_does_not_validate": ["Claude/AgentSight/eBPF capture", "tool-ID-to-PID linkage",
                                        "causal attribution accuracy", "current-run reproducibility"],
        "next_runtime_gate": "Select executable tasks and create separately captured runs before claiming end-to-end generalization.",
    }
    for row in records:
        report["cases_by_dataset"][row["dataset"]] = report["cases_by_dataset"].get(row["dataset"], 0) + 1
    write_json(output / "subset-report.json", report)
    write_json(output / "subset-manifest.json", {
        "cases": [{"dataset": row["dataset"], "split": row.get("split"),
                   "sample_id": row["sample_id"], "source_ref": row["source_ref"],
                   "source_artifact_sha256": row["source_artifact_sha256"],
                   "selected_record_sha256": row["selected_record_sha256"]}
                  for row in records],
        "source_artifacts": list(sources.values()),
    })
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
