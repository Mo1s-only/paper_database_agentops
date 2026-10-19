from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any, Iterable

from .common import (
    base_record,
    evidence,
    json_pointer_token,
    sha256_bytes,
    sha256_text,
    stable_id,
    truth_label,
)


DATASET_VERSION = "0ffbed9"


def _loads_with_narrow_repair(data: bytes) -> tuple[Any, bool]:
    try:
        return json.loads(data), False
    except json.JSONDecodeError:
        text = data.decode("utf-8")
        repaired = re.sub(r",\s*([}\]])", r"\1", text)
        if repaired == text:
            raise
        return json.loads(repaired), True


def _flatten_spans(spans: list[Any], pointer: str, inherited_parent_pointer: str | None = None):
    for index, item in enumerate(spans):
        if not isinstance(item, dict):
            continue
        item_pointer = f"{pointer}/{index}"
        span_id = str(item.get("span_id") or "").strip()
        explicit_parent = str(item.get("parent_span_id") or "").strip() or None
        yield item, item_pointer, explicit_parent, inherited_parent_pointer
        children = item.get("child_spans")
        if isinstance(children, list):
            yield from _flatten_spans(children, f"{item_pointer}/child_spans", item_pointer)


def _annotation_entry(raw_name: str) -> str:
    if "/SWE Bench/" in raw_name:
        prefix = "benchmarking/processed_annotations_swe_bench/"
    elif "/GAIA/" in raw_name:
        prefix = "benchmarking/processed_annotations_gaia/"
    else:
        raise ValueError(f"Unsupported TRAIL split in {raw_name}")
    return prefix + Path(raw_name).name


def adapt_entries(
    *,
    zip_name: str,
    raw_name: str,
    raw_bytes: bytes,
    annotation_name: str,
    annotation_bytes: bytes,
) -> dict[str, Any]:
    raw_digest = sha256_bytes(raw_bytes)
    annotation_digest = sha256_bytes(annotation_bytes)
    raw_obj, raw_repaired = _loads_with_narrow_repair(raw_bytes)
    annotation_obj, annotation_repaired = _loads_with_narrow_repair(annotation_bytes)
    trace_id = str(raw_obj.get("trace_id") or annotation_obj.get("trace_id") or Path(raw_name).stem)
    split = "SWE Bench" if "/SWE Bench/" in raw_name else "GAIA"
    raw_source = f"{zip_name}!{raw_name}"
    annotation_source = f"{zip_name}!{annotation_name}"
    record = base_record(
        dataset_name="TRAIL",
        dataset_version=DATASET_VERSION,
        split=split,
        source_records=[
            {"source_path": raw_source, "sha256": raw_digest},
            {"source_path": annotation_source, "sha256": annotation_digest},
        ],
        run_id=f"trail:{trace_id}",
        session_id=trace_id,
        task_id=trace_id,
    )
    if raw_repaired:
        record["quality"]["warnings"].append(
            "source trace used a narrow trailing-comma JSON repair; original SHA-256 is preserved"
        )
    if annotation_repaired:
        record["quality"]["warnings"].append(
            "source annotation used a narrow trailing-comma JSON repair; original SHA-256 is preserved"
        )

    flattened = list(_flatten_spans(raw_obj.get("spans") or [], "/spans"))
    native_counts: dict[str, int] = {}
    for sequence, (span, _, _, _) in enumerate(flattened):
        native_id = str(span.get("span_id") or "").strip() or stable_id("missing-span", trace_id, sequence)
        native_counts[native_id] = native_counts.get(native_id, 0) + 1

    native_seen: dict[str, int] = {}
    native_to_step_ids: dict[str, list[str]] = {}
    pointer_to_step_id: dict[str, str] = {}
    step_source: dict[str, tuple[dict[str, Any], str, str | None, str | None]] = {}
    services: dict[str, str] = {}
    for sequence, (span, pointer, explicit_parent_id, inherited_parent_pointer) in enumerate(flattened):
        native_id = str(span.get("span_id") or "").strip()
        if not native_id:
            native_id = stable_id("missing-span", trace_id, sequence)
            record["quality"]["warnings"].append(f"span at {pointer} lacked span_id")
        occurrence = native_seen.get(native_id, 0) + 1
        native_seen[native_id] = occurrence
        step_id = f"span:{native_id}"
        if native_counts[native_id] > 1:
            step_id = f"span:{native_id}#{occurrence}"
        native_to_step_ids.setdefault(native_id, []).append(step_id)
        pointer_to_step_id[pointer] = step_id
        step_source[step_id] = (span, pointer, explicit_parent_id, inherited_parent_pointer)
        service = str(span.get("service_name") or "").strip()
        agent_id = service or None
        if service:
            services.setdefault(service, pointer)
        normalized = {key: value for key, value in span.items() if key != "child_spans"}
        record["steps"].append(
            {
                "step_id": step_id,
                "sequence": sequence,
                "agent_id": agent_id,
                "event_type": str(span.get("span_name") or span.get("span_kind") or "span"),
                "timestamp": str(span["timestamp"]) if span.get("timestamp") is not None else None,
                "span_id": native_id,
                "span_id_occurrence": occurrence,
                "status_code": span.get("status_code"),
                "content_sha256": sha256_text(
                    json.dumps(normalized, ensure_ascii=False, sort_keys=True, default=str)
                ),
                "error_labels": [],
                "evidence": [
                    evidence(
                        raw_source,
                        pointer,
                        raw_digest,
                        support="direct",
                        method="OpenTelemetry span record",
                    )
                ],
            }
        )

    for service, pointer in services.items():
        record["agents"].append(
            {
                "agent_id": service,
                "role": "service",
                "evidence": [
                    evidence(
                        raw_source,
                        f"{pointer}/service_name",
                        raw_digest,
                        support="direct",
                        method="span service_name",
                    )
                ],
            }
        )

    relation_keys: set[tuple[str, str]] = set()
    relation_opportunities = 0
    for step_id, (_, pointer, explicit_parent_id, inherited_parent_pointer) in step_source.items():
        parent_step_id = None
        if inherited_parent_pointer:
            parent_step_id = pointer_to_step_id.get(inherited_parent_pointer)
        elif explicit_parent_id:
            candidates = native_to_step_ids.get(explicit_parent_id, [])
            if len(candidates) == 1:
                parent_step_id = candidates[0]
            elif len(candidates) > 1:
                relation_opportunities += 1
                record["quality"]["warnings"].append(
                    f"parent span_id {explicit_parent_id} is ambiguous across {len(candidates)} steps"
                )
                continue
        if not parent_step_id:
            continue
        relation_opportunities += 1
        key = (parent_step_id, step_id)
        if key in relation_keys:
            continue
        relation_keys.add(key)
        record["relations"].append(
            {
                "relation_id": stable_id("relation", trace_id, parent_step_id, step_id, "parent_span"),
                "source_step_id": parent_step_id,
                "target_step_id": step_id,
                "relation_type": "parent_span",
                "evidence": [
                    evidence(
                        raw_source,
                        pointer,
                        raw_digest,
                        support="direct",
                        method="parent_span_id or nested child_spans",
                    )
                ],
            }
        )
    record["quality"]["relation_opportunities"] = relation_opportunities
    record["quality"]["relations_reconstructed"] = len(record["relations"])

    step_output_by_id = {step["step_id"]: step for step in record["steps"]}
    annotated_values: list[dict[str, Any]] = []
    truth_evidence: list[dict[str, str]] = []
    errors = annotation_obj.get("errors") if isinstance(annotation_obj.get("errors"), list) else []
    unmatched = 0
    for index, error in enumerate(errors):
        if not isinstance(error, dict):
            continue
        location = str(error.get("location") or "").strip()
        ev = evidence(
            annotation_source,
            f"/errors/{index}",
            annotation_digest,
            support="direct",
            method="TRAIL annotated error location",
        )
        candidate_step_ids = native_to_step_ids.get(location, [])
        if not candidate_step_ids:
            unmatched += 1
            continue
        label = {
            "step_id": candidate_step_ids[0] if len(candidate_step_ids) == 1 else None,
            "candidate_step_ids": candidate_step_ids,
            "ambiguous": len(candidate_step_ids) > 1,
            "category": error.get("category"),
            "impact": error.get("impact"),
        }
        annotated_values.append(label)
        truth_evidence.append(ev)
        for step_id in candidate_step_ids:
            step_output_by_id[step_id]["error_labels"].append(
                {
                    **{key: error.get(key) for key in ("category", "impact", "description")},
                    "ambiguous_location": len(candidate_step_ids) > 1,
                }
            )
        if len(candidate_step_ids) > 1:
            record["quality"]["warnings"].append(
                f"annotated location {location} matches {len(candidate_step_ids)} duplicate span IDs"
            )

    if annotated_values:
        record["truth"]["responsibility_steps"] = truth_label(
            "partial",
            annotated_values,
            reason=(
                "TRAIL directly annotates error spans, but an error location is not automatically "
                "a decisive responsibility step or root cause."
            ),
            evidence_items=truth_evidence,
        )
    if unmatched:
        record["quality"]["warnings"].append(
            f"{unmatched} annotated error locations did not match a span_id"
        )
    record["truth"]["responsibility_agents"]["reason"] = (
        "TRAIL annotates error spans, not decisive responsibility agents."
    )
    record["truth"]["root_cause_nodes"]["reason"] = (
        "TRAIL error annotations do not distinguish root causes from propagated errors or symptoms."
    )
    record["truth"]["propagation_edges"]["reason"] = (
        "Parent span relations are observed execution structure, not annotated error-propagation truth."
    )
    record["truth"]["causal_paths"]["reason"] = (
        "TRAIL does not directly annotate a complete root-to-symptom causal path."
    )
    record["quality"].update(
        {
            "spans": len(record["steps"]),
            "annotated_errors": len(errors),
            "matched_error_locations": len(annotated_values),
        }
    )
    return record


def iter_records(zip_path: Path) -> Iterable[dict[str, Any]]:
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        raw_names = sorted(
            name
            for name in names
            if name.startswith("benchmarking/data/") and name.endswith(".json")
        )
        for raw_name in raw_names:
            annotation_name = _annotation_entry(raw_name)
            if annotation_name not in names:
                raise FileNotFoundError(f"TRAIL annotation missing for {raw_name}")
            yield adapt_entries(
                zip_name=zip_path.name,
                raw_name=raw_name,
                raw_bytes=archive.read(raw_name),
                annotation_name=annotation_name,
                annotation_bytes=archive.read(annotation_name),
            )
