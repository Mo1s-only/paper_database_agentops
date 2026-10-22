#!/usr/bin/env python3
"""Evaluate gold-label resolvability for the curated public-data subset only.

This evaluator is intentionally separate from align_candidates: public labels and
historical traces are not current-run runtime observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from align_candidates import ROOT, write_json


DEFAULT_SUBSET = ROOT / "lab" / "experiment" / "public_dataset_generalization_20261022_trace_join"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify_sources(cases: list[dict]) -> None:
    for case in cases:
        source_ref = case["source_ref"].removeprefix("Reference paper/datasets/")
        source_name, separator, member = source_ref.partition("::")
        artifact_path = ROOT / "Reference paper" / "datasets" / source_name
        artifact_bytes = artifact_path.read_bytes()
        actual_artifact_hash = hashlib.sha256(artifact_bytes).hexdigest()
        if actual_artifact_hash != case["source_artifact_sha256"]:
            raise ValueError(f"Source artifact hash mismatch: {source_name}")
        if separator:
            with zipfile.ZipFile(artifact_path) as archive:
                record_bytes = archive.read(member)
        else:
            record_bytes = artifact_bytes
        if hashlib.sha256(record_bytes).hexdigest() != case["selected_record_sha256"]:
            raise ValueError(f"Selected record hash mismatch: {case['sample_id']}")


def evaluate(subset_dir: Path = DEFAULT_SUBSET, output: Path | None = None) -> dict:
    if output is None:
        raise ValueError("An explicit output JSON path is required")
    if output.exists():
        raise FileExistsError(f"Refusing to replace existing public mapping evaluation: {output}")

    cases = read_jsonl(subset_dir / "selected-cases.jsonl")
    verify_sources(cases)
    spans = read_jsonl(subset_dir / "trail-normalized-spans.jsonl")
    spans_by_split: dict[str, dict[str, dict]] = {}
    for span in spans:
        spans_by_split.setdefault(span["split"], {})[span["span_id"]] = span

    results = []
    for case in cases:
        dataset, labels = case["dataset"], case["gold_labels"]
        if dataset == "AgentTrace":
            source = ROOT / case["source_ref"]
            trace_record = json.loads(source.read_text(encoding="utf-8"))
            trace = json.loads(trace_record["trace_json"])
            node_ids = {node["id"] for node in trace.get("nodes", [])}
            edges = {(edge["source_id"], edge["target_id"]) for edge in trace.get("edges", [])}
            path = labels["causal_path_node_ids"]
            resolved_nodes = sum(node_id in node_ids for node_id in path)
            resolved_edges = sum((path[i], path[i + 1]) in edges for i in range(len(path) - 1))
            results.append({
                "dataset": dataset, "sample_id": case["sample_id"],
                "label_type": "causal_graph_root_and_path",
                "root_cause_resolves": labels["root_cause_node_id"] in node_ids,
                "error_node_resolves": labels["error_node_id"] in node_ids,
                "path_nodes_resolved": resolved_nodes, "path_node_count": len(path),
                "path_edges_resolved": resolved_edges, "path_edge_count": max(len(path) - 1, 0),
                "result": "resolved" if resolved_nodes == len(path) and resolved_edges == len(path) - 1
                and labels["root_cause_node_id"] in node_ids and labels["error_node_id"] in node_ids else "partial_or_unresolved",
                "runtime_identity_available": False,
            })
        elif dataset == "WhoAndWhen":
            required = ("mistake_agent", "mistake_step", "mistake_reason", "ground_truth")
            present = sum(labels.get(key) is not None for key in required)
            results.append({
                "dataset": dataset, "split": case["split"], "sample_id": case["sample_id"],
                "label_type": "agent_step_attribution",
                "label_fields_present": present, "label_fields_expected": len(required),
                "gold_agent": labels.get("mistake_agent"), "gold_step": labels.get("mistake_step"),
                "explicit_history_step_locator_available": False,
                "result": "labels_present_but_step_not_resolved_to_native_turn_id"
                if present == len(required) else "incomplete_labels",
                "runtime_identity_available": False,
            })
        elif dataset == "TRAIL":
            split_spans = spans_by_split.get(case["split"], {})
            errors = labels["errors"]
            resolved = sum(str(error["location"]) in split_spans for error in errors)
            results.append({
                "dataset": dataset, "split": case["split"], "sample_id": case["sample_id"],
                "label_type": "span_error_location",
                "gold_locations_resolved": resolved, "gold_locations_total": len(errors),
                "result": "resolved" if resolved == len(errors) else "partial_or_unresolved",
                "runtime_identity_available": False,
            })
        else:
            raise ValueError(f"Unsupported public dataset family: {dataset}")

    out_dir = subset_dir
    adapter_records = spans
    records_path = out_dir / "trail-normalized-spans.jsonl"
    return {
        "schema_version": "public-dataset-label-mapping-evaluation-v0.1",
        "case_count": len(results),
        "dataset_families": sorted({row["dataset"] for row in results}),
        "source_integrity_verified_count": len(cases),
        "case_results": results,
        "trail_normalized_span_count": len(adapter_records),
        "trail_normalized_spans_sha256": hashlib.sha256(records_path.read_bytes()).hexdigest(),
        "claim_boundary": "Public-label structural resolvability only; not current AgentSight/eBPF capture, runtime cross-layer linkage, or attribution accuracy.",
        "api_calls": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subset-dir", type=Path, default=DEFAULT_SUBSET)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(args.subset_dir, args.output)
    write_json(args.output, report)
    print(json.dumps({"case_count": report["case_count"], "datasets": report["dataset_families"],
                      "claim_boundary": report["claim_boundary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
