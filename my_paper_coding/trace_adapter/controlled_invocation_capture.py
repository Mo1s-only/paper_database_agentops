#!/usr/bin/env python3
"""Create and finalize a privacy-preserving model invocation evidence sidecar."""
from __future__ import annotations

import hashlib
import json
import time
import uuid

from model_invocation_context import VERSION, validate_context


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_tool_schema(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def prepare_request(*, run_id: str, session_id: str, agent_id: str,
                    model_id: str, model_version: str, temperature: float,
                    top_p: float, system_prompt: str, tool_schema) -> dict:
    """Freeze settings and hashes immediately before a controlled API request."""
    identifiers = (run_id, session_id, agent_id, model_id, model_version)
    if not all(isinstance(value, str) and value.strip() for value in identifiers):
        raise ValueError("Controlled invocation requires explicit identities and model version")
    if not isinstance(system_prompt, str):
        raise ValueError("System prompt must be text")
    if (isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or
            temperature < 0):
        raise ValueError("Invalid sampling temperature")
    if (isinstance(top_p, bool) or not isinstance(top_p, (int, float)) or
            not 0 <= top_p <= 1):
        raise ValueError("Invalid sampling top_p")
    return {
        "schema_version": "agentops-model-request-manifest-v0.1",
        "run_id": run_id,
        "session_id": session_id,
        "agent_id": agent_id,
        "request_id": str(uuid.uuid4()),
        "model_id": model_id,
        "model_version": model_version,
        "sampling_temperature": temperature,
        "sampling_top_p": top_p,
        "system_prompt_sha256": hash_text(system_prompt),
        "tool_schema_sha256": hash_text(canonical_tool_schema(tool_schema)),
        "request_monotonic_ns": time.monotonic_ns(),
    }


def finalize_response(request: dict, response_id: str,
                      response_monotonic_ns: int | None = None) -> dict:
    """Bind a native provider response ID to the frozen request manifest."""
    if not isinstance(response_id, str) or not response_id.strip():
        raise ValueError("Native response ID is required")
    response_time = time.monotonic_ns() if response_monotonic_ns is None else response_monotonic_ns
    value = {
        "schema_version": VERSION,
        "evidence_kind": "runtime_observed",
        "run_id": request["run_id"],
        "session_id": request["session_id"],
        "agent_id": request["agent_id"],
        "request_id": request["request_id"],
        "response_id": response_id,
        "model_id": request["model_id"],
        "model_version": request["model_version"],
        "sampling_temperature": request["sampling_temperature"],
        "sampling_top_p": request["sampling_top_p"],
        "system_prompt_sha256": request["system_prompt_sha256"],
        "tool_schema_sha256": request["tool_schema_sha256"],
        "request_monotonic_ns": request["request_monotonic_ns"],
        "response_monotonic_ns": response_time,
        "pairing_method": "native_response_id_bound_to_client_request_id",
        "pairing_evidence": [
            f"client.request_id={request['request_id']}",
            f"provider.response_id={response_id}",
        ],
    }
    validate_context(value)
    return value
