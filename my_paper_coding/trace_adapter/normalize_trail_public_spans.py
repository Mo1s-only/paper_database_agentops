#!/usr/bin/env python3
"""Normalize selected historical TRAIL spans without inventing runtime identities."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from align_candidates import ROOT, write_json


ARCHIVE = ROOT / "Reference paper" / "datasets" / "shared_data" / "TRAIL_benchmarking_148_traces.zip"
CASES = {
    "GAIA": "0035f455b3ff2295167a844f04d85d34",
    "SWE-bench": "0e6f7928953ab5a568bae640ce915cc3",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def flatten_spans(trace: dict) -> list[tuple[dict, str | None]]:
    flattened: list[tuple[dict, str | None]] = []
    pending = [(span, None) for span in reversed(trace.get("spans", []))]
    while pending:
        span, parent_id = pending.pop()
        flattened.append((span, parent_id))
        current_id = span.get("span_id")
        for child in reversed(span.get("child_spans", [])):
            pending.append((child, str(current_id) if current_id else parent_id))
    return flattened


def _semantic_span(span: dict, parent_id: str | None, *, dataset: str,
                   trace_id: str, member: str, trace_sha256: str) -> dict:
    attrs = span.get("span_attributes") or {}
    llm_attribute_names = sorted(key for key in attrs if key.startswith("llm."))
    return {
        "record_type": "public.semantic_span",
        "evidence_status": "historical_public_trace",
        "dataset": "TRAIL",
        "split": dataset,
        "trace_id": trace_id,
        "span_id": str(span["span_id"]),
        "parent_span_id": str(span.get("parent_span_id") or parent_id) if (span.get("parent_span_id") or parent_id) else None,
        "span_name": span.get("span_name"),
        "span_kind": span.get("span_kind"),
        "openinference_kind": attrs.get("openinference.span.kind"),
        "service_name": span.get("service_name"),
        "timestamp": span.get("timestamp"),
        "duration": span.get("duration"),
        "status_code": span.get("status_code"),
        "tool_name": attrs.get("tool.name"),
        "llm_model_name": attrs.get("llm.model_name"),
        "llm_attribute_names": llm_attribute_names,
        "input_present": any(key in attrs for key in ("input.value", "llm.input_messages.0.message.content")),
        "output_present": any(key in attrs for key in ("output.value", "llm.output_messages.0.message.content")),
        "identity": {"agent_id": None, "step_id": None, "tool_call_id": None,
                     "pid": None, "ppid": None, "pid_namespace": None},
        "source": {"archive": "Reference paper/datasets/shared_data/TRAIL_benchmarking_148_traces.zip",
                   "member": member, "trace_record_sha256": trace_sha256},
    }


def normalize(archive_path: Path = ARCHIVE, output: Path | None = None) -> dict:
    if output is None:
        raise ValueError("An explicit output JSONL path is required")
    report_path = output.with_name("trail-normalization-report.json")
    if output.exists() or report_path.exists():
        raise FileExistsError(f"Refusing to replace existing normalized output or report: {output}")

    records: list[dict] = []
    cases_report = []
    with zipfile.ZipFile(archive_path) as archive:
        for split, sample_id in CASES.items():
            family = "GAIA" if split == "GAIA" else "SWE Bench"
            member = f"benchmarking/data/{family}/{sample_id}.json"
            raw = archive.read(member)
            trace = json.loads(raw)
            if trace.get("trace_id") != sample_id:
                raise ValueError(f"Trace ID mismatch for {member}")
            flattened = flatten_spans(trace)
            ids = [str(span.get("span_id", "")) for span, _ in flattened]
            if any(not value for value in ids) or len(ids) != len(set(ids)):
                raise ValueError(f"Missing or duplicate span ID in {member}")
            trace_hash = sha256_bytes(raw)
            records.extend(_semantic_span(span, parent_id, dataset=split,
                                          trace_id=sample_id, member=member,
                                          trace_sha256=trace_hash)
                           for span, parent_id in flattened)
            cases_report.append({"split": split, "sample_id": sample_id,
                                 "span_count": len(flattened),
                                 "trace_record_sha256": trace_hash,
                                 "span_ids": ids})

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    report = {
        "schema_version": "trail-public-semantic-span-v0.1",
        "record_count": len(records),
        "cases": cases_report,
        "identity_policy": "Historical public traces do not assert current tool IDs or OS process identity; absent fields remain null.",
        "excluded_content": "Raw prompt, completion, tool arguments and tool output bodies are not copied; only selected metadata and attribute-presence indicators are retained.",
        "api_calls": 0,
    }
    write_json(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(normalize(args.archive, args.output), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
