from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from . import SCHEMA_VERSION


TRUTH_FIELDS = (
    "responsibility_agents",
    "responsibility_steps",
    "root_cause_nodes",
    "propagation_edges",
    "causal_paths",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def stable_id(prefix: str, *parts: object) -> str:
    material = "\x1f".join(str(part) for part in parts)
    return f"{prefix}:{sha256_text(material)[:20]}"


def json_pointer_token(value: object) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")


def evidence(
    source_path: str,
    json_pointer: str,
    record_sha256: str,
    *,
    support: str,
    method: str,
) -> dict[str, str]:
    return {
        "source_path": source_path,
        "json_pointer": json_pointer,
        "record_sha256": record_sha256,
        "support": support,
        "method": method,
    }


def truth_label(
    state: str,
    values: list[Any] | None = None,
    *,
    reason: str,
    evidence_items: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "state": state,
        "values": values or [],
        "reason": reason,
        "evidence": evidence_items or [],
    }


def abstain(reason: str) -> dict[str, Any]:
    return truth_label("abstain", reason=reason)


def base_record(
    *,
    dataset_name: str,
    dataset_version: str,
    split: str,
    source_records: list[dict[str, str]],
    run_id: str,
    session_id: str | None,
    task_id: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": {
            "name": dataset_name,
            "version": dataset_version,
            "split": split,
        },
        "run": {
            "run_id": run_id,
            "session_id": session_id,
            "task_id": task_id,
        },
        "agents": [],
        "steps": [],
        "relations": [],
        "truth": {field: abstain("adapter did not assign this label") for field in TRUTH_FIELDS},
        "provenance": {
            "adapter": f"{dataset_name}-adapter-v0.1",
            "source_records": source_records,
        },
        "quality": {
            "warnings": [],
            "relation_opportunities": 0,
            "relations_reconstructed": 0,
        },
    }


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)

