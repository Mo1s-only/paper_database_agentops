#!/usr/bin/env python3
"""Privacy-preserving invocation metadata required before Watson-style reconstruction."""
from __future__ import annotations

import json
from pathlib import Path


VERSION = "agentops-model-invocation-context-v0.1"
KEYS = {
    "schema_version", "evidence_kind", "run_id", "session_id", "agent_id",
    "request_id", "response_id", "model_id", "model_version",
    "sampling_temperature", "sampling_top_p", "system_prompt_sha256",
    "tool_schema_sha256", "request_monotonic_ns", "response_monotonic_ns",
    "pairing_method", "pairing_evidence",
}


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def sha256_text(value):
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value)


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_context(value: dict) -> None:
    if not isinstance(value, dict) or set(value) != KEYS:
        raise ValueError("Invocation context requires exactly the v0.1 fields")
    if value["schema_version"] != VERSION or value["evidence_kind"] != "runtime_observed":
        raise ValueError("Invocation context must be runtime-observed v0.1 evidence")
    for field in ("run_id", "session_id", "agent_id", "request_id", "response_id",
                  "model_id", "model_version", "pairing_method"):
        if not nonempty(value[field]):
            raise ValueError(f"Missing invocation identifier: {field}")
    if not number(value["sampling_temperature"]) or value["sampling_temperature"] < 0:
        raise ValueError("Invalid sampling temperature")
    if not number(value["sampling_top_p"]) or not 0 <= value["sampling_top_p"] <= 1:
        raise ValueError("Invalid sampling top_p")
    for field in ("system_prompt_sha256", "tool_schema_sha256"):
        if not sha256_text(value[field]):
            raise ValueError(f"Invalid SHA256 field: {field}")
    for field in ("request_monotonic_ns", "response_monotonic_ns"):
        if not isinstance(value[field], int) or isinstance(value[field], bool) or value[field] < 0:
            raise ValueError(f"Invalid monotonic time: {field}")
    if value["response_monotonic_ns"] < value["request_monotonic_ns"]:
        raise ValueError("Response precedes request")
    evidence = value["pairing_evidence"]
    if not isinstance(evidence, list) or not evidence or not all(nonempty(item) for item in evidence):
        raise ValueError("Request/response pairing requires explicit evidence")
    if len(evidence) != len(set(evidence)):
        raise ValueError("Pairing evidence must be unique")


def validate_contexts(values: list[dict], run_id: str, session_ids: set[str]) -> dict:
    seen = set()
    covered_sessions = set()
    for value in values:
        validate_context(value)
        if value["run_id"] != run_id or value["session_id"] not in session_ids:
            raise ValueError("Invocation context does not belong to the event stream")
        key = (value["request_id"], value["response_id"])
        if key in seen:
            raise ValueError("Duplicate request/response pair")
        seen.add(key)
        covered_sessions.add(value["session_id"])
    return {
        "context_count": len(values),
        "covered_session_count": len(covered_sessions),
        "all_sessions_covered": bool(values) and covered_sessions == session_ids,
    }


def read_contexts(path: Path) -> list[dict]:
    values = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            raise ValueError("Blank invocation context line")
        values.append(json.loads(line))
    return values
