#!/usr/bin/env python3
"""Build a read-only, provenance-preserving index of existing experiment runs.

The index intentionally does not synthesize trace events or copy raw logs. It
only inventories the evidence that a future Trace Adapter may consume.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "structured_runs"

ROOTS = [
    WORKSPACE / "my_paper_coding" / "failure_pilot" / "results",
    WORKSPACE / "my_paper_coding" / "p0_pairing" / "results",
    WORKSPACE / "my_paper_coding" / "evaluation_gate" / "results",
]


def rel(path: Path) -> str:
    return path.resolve().relative_to(WORKSPACE.resolve()).as_posix()


def sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def category(path: Path) -> str:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if name in {"session.db", "session.db-shm", "session.db-wal", "raw-stream.log", "record.log", "db-rows.txt"}:
        return "raw_observation"
    if name.startswith("report-") or name.startswith("report_") or name in {"ssl-http.jsonl", "ssl-http.err"}:
        return "raw_observation"
    if name.startswith("claude") or name in {"agent-exit.txt", "agent-a-exit.txt", "agent-b-exit.txt"}:
        return "app_log"
    if name in {"route.json", "decision.json", "marker.txt"} or "workspace" in path.parts:
        return "task_context"
    if "ground_truth" in name or name.startswith("truth") or "oracle" in name:
        return "validator"
    if name in {
        "trace.jsonl", "analysis.json", "counterfactual.json", "normalization-summary.json",
        "pairing-analysis.json", "capture-summary.json", "cost.json", "matrix-summary.json",
        "adapter-smoke-report.json",
    } or "summary" in name:
        return "derived"
    if name in {"run-info.txt", "run.json", "metadata.json"} or name.endswith("-exit.txt"):
        return "metadata"
    if suffix in {".jsonl", ".json", ".log", ".txt", ".db"}:
        return "unclassified"
    return "unclassified"


def format_for(path: Path) -> str:
    lower = path.name.lower()
    if lower.endswith(".jsonl"):
        return "jsonl"
    if lower.endswith(".json"):
        return "json"
    if lower.endswith(".db") or ".db-" in lower:
        return "sqlite_or_sqlite_sidecar"
    if lower.endswith(".log") or lower.endswith(".txt"):
        return "text"
    return path.suffix.lower().lstrip(".") or "binary"


def parse_json_signals(path: Path) -> dict[str, Any]:
    """Extract non-content metadata from JSON artifacts when possible."""
    value = read_json(path)
    if not isinstance(value, dict):
        return {}
    signals: dict[str, Any] = {}
    for key in ("session_id", "sessionId", "model", "stop_reason", "stopReason", "result", "is_error"):
        if key in value and key != "result":
            signals[key] = value[key]
    usage = value.get("usage")
    if isinstance(usage, dict):
        signals["usage"] = {
            k: usage[k] for k in ("input_tokens", "output_tokens", "cache_read_input_tokens") if k in usage
        }
    for key in ("cost_usd", "total_cost_usd", "total_cost"):
        if key in value:
            signals[key] = value[key]
    return signals


def extract_text_signals(path: Path) -> dict[str, Any]:
    """Read only small metadata hints; never copy prompt/response content."""
    if path.stat().st_size > 2 * 1024 * 1024:
        return {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    signals: dict[str, Any] = {}
    model = re.search(r'"model"\s*:\s*"([^"]+)"', text)
    if model:
        signals["model"] = model.group(1)
    session = re.search(r'"session[_-]?id"\s*:\s*"([^"]+)"', text)
    if session:
        signals["session_id"] = session.group(1)
    return signals


def direct_files(path: Path) -> list[Path]:
    return sorted((p for p in path.iterdir() if p.is_file()), key=lambda p: p.name.lower())


def candidate_dirs() -> list[Path]:
    found: set[Path] = set()
    for root in ROOTS:
        if not root.exists():
            continue
        for directory in [root, *[p for p in root.rglob("*") if p.is_dir()]]:
            # Workspace files are task artifacts belonging to their parent run,
            # not independent experimental runs.
            if directory.name.lower() == "workspace":
                continue
            files = direct_files(directory)
            if files:
                found.add(directory.resolve())
    return sorted(found, key=lambda p: rel(p))


def experiment_family(path: Path) -> str:
    path_text = path.as_posix()
    if "/failure_pilot/" in path_text:
        return "failure_pilot"
    if "/p0_pairing/" in path_text:
        return "p0_pairing"
    if "/evaluation_gate/" in path_text:
        return "evaluation_gate"
    return "unknown"


def make_manifest(run_dir: Path) -> dict[str, Any]:
    files = direct_files(run_dir)
    # Include all descendants as evidence while preserving the source tree.
    all_files = sorted((p for p in run_dir.rglob("*") if p.is_file()), key=lambda p: rel(p))
    artifacts: list[dict[str, Any]] = []
    aggregate: dict[str, Any] = {"models": [], "session_ids": [], "costs": []}
    for file in all_files:
        item: dict[str, Any] = {
            "path": rel(file),
            "path_from_run": file.relative_to(run_dir).as_posix(),
            "category": category(file),
            "format": format_for(file),
            "bytes": file.stat().st_size,
            "sha256": sha256(file),
            "parse_status": "inventory_only",
        }
        if file.suffix.lower() == ".json":
            signals = parse_json_signals(file)
        elif file.suffix.lower() in {".log", ".txt", ".jsonl"}:
            signals = extract_text_signals(file)
        else:
            signals = {}
        if signals:
            item["signals"] = signals
            if signals.get("model") and signals["model"] not in aggregate["models"]:
                aggregate["models"].append(signals["model"])
            session_id = signals.get("session_id") or signals.get("sessionId")
            if session_id and session_id not in aggregate["session_ids"]:
                aggregate["session_ids"].append(session_id)
            for key in ("cost_usd", "total_cost_usd", "total_cost"):
                if key in signals:
                    aggregate["costs"].append({"artifact": rel(file), "field": key, "value": signals[key]})
        artifacts.append(item)

    categories = {item["category"] for item in artifacts}
    warnings: list[str] = []
    if "raw_observation" not in categories:
        warnings.append("missing_raw_observation")
    if "app_log" not in categories:
        warnings.append("missing_app_log")
    if "validator" not in categories:
        warnings.append("missing_independent_validator")
    if "derived" not in categories:
        warnings.append("missing_derived_outputs")
    has_children = any(p.is_dir() for p in run_dir.iterdir())
    direct_categories = {category(p) for p in files}
    # Batch folders hold a matrix summary and child runs. They are indexed for
    # provenance, but should not be fed to the event-level adapter as a run.
    run_kind = "batch" if has_children and not {"raw_observation", "app_log", "validator", "task_context"}.intersection(direct_categories) else "run"
    run_id = run_dir.name
    return {
        "schema_version": "trace-run-manifest-v0.2",
        "run_id": run_id,
        "run_kind": run_kind,
        "experiment_family": experiment_family(run_dir),
        "source_root": rel(run_dir),
        "indexed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "framework": "Claude Code CLI" if "app_log" in categories else "unknown_or_synthetic",
        "signals": aggregate,
        "evidence_categories": sorted(categories),
        "artifacts": artifacts,
        "completeness": {
            "raw_observation": "raw_observation" in categories,
            "application_log": "app_log" in categories,
            "task_context": "task_context" in categories,
            "independent_validator": "validator" in categories,
            "derived_outputs": "derived" in categories,
        },
        "warnings": warnings,
        "adapter_contract": {
            "raw_is_observation_only": True,
            "validator_is_independent_of_trace": True,
            "derived_outputs_are_not_ground_truth": True,
            "raw_content_may_contain_prompts_or_secrets": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="manifest output directory")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifests: list[dict[str, Any]] = []
    for run_dir in candidate_dirs():
        manifest = make_manifest(run_dir)
        manifests.append(manifest)
        target = output / manifest["experiment_family"] / manifest["run_id"] / "run.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifests.sort(key=lambda item: (item["experiment_family"], item["run_id"]))
    index = {
        "schema_version": "trace-run-index-v0.2",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "workspace": ".",
        "source_roots": [rel(root) for root in ROOTS if root.exists()],
        "run_count": len(manifests),
        "runs": [
            {
                "run_id": item["run_id"],
                "run_kind": item["run_kind"],
                "experiment_family": item["experiment_family"],
                "manifest": (Path(item["experiment_family"]) / item["run_id"] / "run.json").as_posix(),
                "source_root": item["source_root"],
                "warnings": item["warnings"],
            }
            for item in manifests
        ],
    }
    (output / "run-index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output / "run-index.jsonl").open("w", encoding="utf-8") as handle:
        for item in manifests:
            handle.write(json.dumps({
                "run_id": item["run_id"],
                "run_kind": item["run_kind"],
                "experiment_family": item["experiment_family"],
                "manifest": (Path(item["experiment_family"]) / item["run_id"] / "run.json").as_posix(),
                "source_root": item["source_root"],
                "warnings": item["warnings"],
            }, ensure_ascii=False) + "\n")
    print(f"indexed {len(manifests)} directories -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
