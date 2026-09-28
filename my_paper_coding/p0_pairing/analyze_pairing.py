#!/usr/bin/env python3
"""Conservatively score one marker-based AgentSight pairing capture.

The marker is the only ground truth used here.  This script deliberately does
not infer arbitrary request/response pairs from timestamp proximity.  A pair
must contain the same marker, use the same observed pid/tid, and have the
response after the request.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], int, int]:
    events: list[dict[str, Any]] = []
    non_json_lines = 0
    malformed_json_objects = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                non_json_lines += 1
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                if stripped.startswith("{"):
                    malformed_json_objects += 1
                else:
                    non_json_lines += 1
                continue
            if isinstance(value, dict):
                events.append(value)
    return events, non_json_lines, malformed_json_objects


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def event_text(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False)


def timestamp(event: dict[str, Any]) -> int | None:
    value = event.get("timestamp")
    return value if isinstance(value, int) else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    run_dir = args.run_dir
    marker = (run_dir / "marker.txt").read_text(encoding="utf-8").strip()
    events, non_json_lines, malformed_json_objects = load_jsonl(
        run_dir / "ssl-http.jsonl"
    )

    source_counts = Counter(str(event.get("source")) for event in events)
    message_counts = Counter(
        str((event.get("data") or {}).get("message_type")) for event in events
    )

    requests: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    for event in events:
        data = event.get("data") or {}
        source = event.get("source")
        if (
            source == "http_parser"
            and data.get("message_type") == "request"
            and data.get("method") == "POST"
            and "/messages" in str(data.get("path"))
            and marker in str(data.get("body"))
        ):
            requests.append(event)

        # The HTTP response body can be split across TLS reads.  The SSE
        # processor is therefore the authoritative response-side marker.
        if (
            source == "sse_processor"
            and marker in str(data.get("text_content"))
        ):
            responses.append(event)

    pair_candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for request in requests:
        request_data = request.get("data") or {}
        request_key = (request.get("pid"), request_data.get("tid"))
        request_time = timestamp(request)
        for response in responses:
            response_data = response.get("data") or {}
            response_key = (response.get("pid"), response_data.get("tid"))
            response_time = timestamp(response)
            if request_key != response_key:
                continue
            if request_time is None or response_time is None:
                continue
            if response_time >= request_time:
                pair_candidates.append((request, response))

    expected_pairs = 1
    pair_matches = 1 if len(pair_candidates) == 1 else 0
    marker_precision = pair_matches / len(pair_candidates) if pair_candidates else 0.0
    marker_recall = pair_matches / expected_pairs

    claude = read_json(run_dir / "claude.json")
    agent_exit = (run_dir / "agent-exit.txt").read_text(encoding="utf-8").strip()
    agent_success = agent_exit == "0" and bool(claude and claude.get("result") == marker)

    response_latency_ms = None
    if pair_matches:
        response_latency_ms = timestamp(pair_candidates[0][1]) - timestamp(pair_candidates[0][0])

    result: dict[str, Any] = {
        "schema_version": 1,
        "run_dir": str(run_dir),
        "marker": marker,
        "agent_success": agent_success,
        "agent_exit_code": agent_exit,
        "json_lines": len(events),
        "non_json_lines": non_json_lines,
        "malformed_json_objects": malformed_json_objects,
        "source_counts": dict(source_counts),
        "message_type_counts": dict(message_counts),
        "marker_request_hits": len(requests),
        "marker_response_hits": len(responses),
        "marker_pair_candidates": len(pair_candidates),
        "marker_pair_matches": pair_matches,
        "marker_pair_precision": marker_precision,
        "marker_pair_recall": marker_recall,
        "response_latency_ms": response_latency_ms,
        "gate_pass": bool(
            agent_success
            and len(requests) == 1
            and len(responses) == 1
            and pair_matches == 1
            and malformed_json_objects == 0
        ),
        "interpretation": (
            "Marker-specific pairing evidence only; this is not a general request-response recall estimate."
        ),
    }

    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    target = args.json_out or run_dir / "pairing-analysis.json"
    target.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
