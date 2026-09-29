#!/usr/bin/env python3
"""Create provenance-first, non-authoritative event records from indexed runs.

This script never invents timestamps, agent IDs, parent edges, or task outcomes.
Every emitted record points to the original file and line. Existing trace.jsonl
records are marked as derived so they cannot silently become ground truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX = Path(__file__).resolve().parent / "structured_runs" / "run-index.json"


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def load_json_line(line: str) -> dict[str, Any] | None:
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def app_result_record(value: dict[str, Any], source: Path, line_no: int) -> dict[str, Any]:
    result = value.get("result")
    record: dict[str, Any] = {
        "record_type": "application.result",
        "evidence_status": "observed",
        "event_id": value.get("uuid"),
        "session_id": value.get("session_id"),
        "timestamp": None,
        "agent_id": None,
        "step_id": None,
        "tool_call_id": None,
        "status": "error" if value.get("is_error") else value.get("subtype") or value.get("stop_reason"),
        "model": value.get("model"),
        "usage": value.get("usage"),
        "cost_usd": value.get("total_cost_usd"),
        "result_summary": {
            "present": isinstance(result, str),
            "length": len(result) if isinstance(result, str) else 0,
            "sha256": digest_text(result) if isinstance(result, str) else None,
        },
        "source": {"path": rel(source), "line": line_no, "role": "app_log"},
        "limitations": [
            "final_result_record_only",
            "no_step_or_tool_events_in_source",
            "timestamp_unavailable_in_source",
        ],
    }
    if value.get("modelUsage"):
        record["model_usage"] = value["modelUsage"]
    return record


def http_record(value: dict[str, Any], source: Path, line_no: int) -> dict[str, Any]:
    data = value.get("data") if isinstance(value.get("data"), dict) else {}
    record = {
        "record_type": "network.http",
        "evidence_status": "observed",
        "event_id": None,
        "session_id": None,
        "timestamp": value.get("timestamp"),
        "agent_id": None,
        "step_id": None,
        "tool_call_id": None,
        "pid": value.get("pid"),
        "tid": data.get("tid"),
        "message_type": data.get("message_type"),
        "method": data.get("method"),
        "path": data.get("path"),
        "status_code": data.get("status_code"),
        "content_length": data.get("content_length"),
        "source": {"path": rel(source), "line": line_no, "role": "raw_observation"},
        "limitations": [
            "application_session_not_present_in_source",
            "agent_step_not_present_in_source",
        ],
    }
    return record


def derived_trace_record(value: dict[str, Any], source: Path, line_no: int) -> dict[str, Any]:
    return {
        "record_type": "derived.trace_event",
        "evidence_status": "derived_untrusted",
        "event_id": value.get("event_id"),
        "session_id": value.get("session_id"),
        "timestamp": value.get("timestamp"),
        "agent_id": value.get("agent_id"),
        "step_id": value.get("step_id"),
        "tool_call_id": value.get("tool_call_id"),
        "event_type": value.get("event_type"),
        "status": value.get("status"),
        "parent_event_id": value.get("parent_event_id"),
        "source": {"path": rel(source), "line": line_no, "role": "derived"},
        "limitations": [
            "not_reconstructed_from_raw_evidence",
            "must_not_be_used_as_ground_truth",
        ],
    }


def json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"encoding": "base64", "length": len(value), "sha256": hashlib.sha256(value).hexdigest()}
    return value


def normalize_sqlite(source: Path, output) -> tuple[int, int]:
    """Expose AgentSight tables as observed records with table/row provenance."""
    emitted = skipped = 0
    try:
        connection = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        tables = [row[0] for row in connection.execute(
            "select name from sqlite_master where type='table' order by name"
        )]
        for table in tables:
            columns = [row[1] for row in connection.execute(f"pragma table_info({table})")]
            if not columns:
                continue
            query = f"select rowid, * from {table}" if "id" not in columns else f"select * from {table}"
            for row in connection.execute(query):
                if "rowid" in query:
                    row_id, *values = row
                else:
                    values = list(row)
                    row_id = values[columns.index("id")] if "id" in columns else None
                fields = {name: json_safe(value) for name, value in zip(columns, values)}
                record = {
                    "record_type": f"agentsight.{table}",
                    "evidence_status": "observed",
                    "event_id": fields.get("id") or f"{table}:{row_id}",
                    "timestamp": fields.get("timestamp_ms") or fields.get("start_timestamp_ms"),
                    "agent_id": None,
                    "step_id": None,
                    "tool_call_id": fields.get("tool_call_id"),
                    "pid": fields.get("pid"),
                    "fields": fields,
                    "source": {"path": rel(source), "table": table, "row": row_id, "role": "raw_observation"},
                    "limitations": [
                        "agent_and_step_identity_not_present_in_agentsight_row",
                        "cross_layer_alignment_not_yet_performed",
                    ],
                }
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
                emitted += 1
        connection.close()
    except (OSError, sqlite3.Error):
        skipped += 1
    return emitted, skipped


def normalize_artifact(run_dir: Path, artifact: dict[str, Any], output) -> tuple[int, int]:
    source = ROOT / artifact["path"]
    name = source.name.lower()
    if not source.exists():
        return 0, 0
    if source.suffix.lower() == ".db":
        return normalize_sqlite(source, output)
    if source.suffix.lower() not in {".json", ".jsonl", ".log", ".txt"}:
        return 0, 0
    emitted = skipped = 0
    try:
        lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 0, 0
    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        value = load_json_line(line)
        record = None
        if name == "trace.jsonl" and value:
            record = derived_trace_record(value, source, line_no)
        elif name == "ssl-http.jsonl" and value and "data" in value:
            record = http_record(value, source, line_no)
        elif name.startswith("claude") and value and ("session_id" in value or "result" in value):
            record = app_result_record(value, source, line_no)
        if record is None:
            skipped += 1
            continue
        output.write(json.dumps(record, ensure_ascii=False) + "\n")
        emitted += 1
    return emitted, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--output", type=Path, default=DEFAULT_INDEX.parent / "normalized")
    args = parser.parse_args()
    index = json.loads(args.index.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": "trace-adapter-normalized-v0.1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_index": rel(args.index),
        "runs": [],
    }
    for entry in index["runs"]:
        if entry["run_kind"] != "run":
            continue
        manifest_path = args.index.parent / entry["manifest"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        target_dir = args.output / entry["experiment_family"] / entry["run_id"]
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "evidence-events.jsonl"
        emitted = skipped = 0
        with target.open("w", encoding="utf-8") as output:
            for artifact in manifest["artifacts"]:
                count, skipped_count = normalize_artifact(ROOT / manifest["source_root"], artifact, output)
                emitted += count
                skipped += skipped_count
        report["runs"].append({
            "run_id": entry["run_id"],
            "experiment_family": entry["experiment_family"],
            "manifest": entry["manifest"],
            "normalized_events": (Path("normalized") / entry["experiment_family"] / entry["run_id"] / "evidence-events.jsonl").as_posix(),
            "emitted_records": emitted,
            "skipped_non_event_lines": skipped,
            "authority": "evidence_records_only; no synthetic event completion",
        })
    (args.output / "normalization-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"normalized {len(report['runs'])} runs -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
