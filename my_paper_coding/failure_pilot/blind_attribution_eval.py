#!/usr/bin/env python3
"""Label-blind attribution and a separate post-hoc scorer.

The prediction path accepts only a trace. It deliberately has no task/fault
parameter and never opens a ground-truth file. Run `predict` and `score` as
separate CLI invocations so prediction is frozen before labels are read.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _event_index(trace: list[dict[str, Any]]) -> dict[str, dict[str, Any]] | None:
    index: dict[str, dict[str, Any]] = {}
    trace_run_ids = {event.get("run_id") for event in trace if event.get("run_id") is not None}
    if len(trace_run_ids) > 1:
        return None
    for event in trace:
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id or event_id in index:
            return None
        index[event_id] = event
    return index


def _candidates(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return observable contract/error candidates without consulting labels."""
    required: dict[str, Any] = {}
    for event in trace:
        if event.get("event_type") == "task.start":
            summary = event.get("output_summary")
            if isinstance(summary, dict):
                for key, value in summary.items():
                    if key.startswith("required_"):
                        required[key.removeprefix("required_")] = value
                    else:
                        # Some adapters store the task contract directly in task.start.
                        required.setdefault(key, value)

    candidates = []
    for event in trace:
        if event.get("event_type") == "tool.result":
            if event.get("status") == "error":
                candidates.append({"event": event, "basis": "explicit_tool_error"})
                continue
            output = event.get("output_summary")
            if event.get("status") == "success" and isinstance(output, dict):
                mismatches = [
                    key for key, expected in required.items()
                    if key in output and output[key] != expected
                ]
                if mismatches:
                    candidates.append({
                        "event": event,
                        "basis": "task_contract_mismatch",
                        "mismatched_fields": sorted(mismatches),
                    })
        elif event.get("event_type") == "route.decision":
            inp = event.get("input_summary")
            output = event.get("output_summary")
            if isinstance(inp, dict) and isinstance(output, dict):
                expected_role = inp.get("required_role")
                assigned_role = output.get("assigned_role")
                if expected_role is not None and assigned_role is not None and expected_role != assigned_role:
                    candidates.append({
                        "event": event,
                        "basis": "route_contract_mismatch",
                        "mismatched_fields": ["assigned_role"],
                    })
    return candidates


def predict(trace: list[dict[str, Any]]) -> dict[str, Any]:
    """Predict one responsible action from observed events only; otherwise abstain."""
    index = _event_index(trace)
    if index is None:
        return {"prediction_status": "abstain", "abstain_reason": "invalid_or_duplicate_event_id", "candidate_count": 0}

    candidates = _candidates(trace)
    if not candidates:
        return {"prediction_status": "abstain", "abstain_reason": "no_supported_candidate", "candidate_count": 0}
    if len(candidates) != 1:
        return {
            "prediction_status": "abstain",
            "abstain_reason": "multiple_supported_candidates",
            "candidate_count": len(candidates),
            "candidate_event_ids": [item["event"].get("event_id") for item in candidates],
        }

    candidate_info = candidates[0]
    candidate = candidate_info["event"]
    candidate_id = candidate["event_id"]
    parent_id = candidate.get("parent_event_id")
    parent = index.get(parent_id) if isinstance(parent_id, str) else None
    if parent is None:
        return {
            "prediction_status": "abstain",
            "abstain_reason": "candidate_parent_missing",
            "candidate_count": 1,
            "candidate_event_id": candidate_id,
        }

    if candidate.get("event_type") == "tool.result":
        if parent.get("event_type") != "tool.call":
            return {
                "prediction_status": "abstain",
                "abstain_reason": "tool_result_parent_not_tool_call",
                "candidate_count": 1,
                "candidate_event_id": candidate_id,
            }
        action = parent
    else:
        action = candidate

    required_fields = (action.get("agent_id"), action.get("step_id"), parent.get("event_id"))
    if not all(isinstance(value, str) and value for value in required_fields):
        return {
            "prediction_status": "abstain",
            "abstain_reason": "responsibility_fields_missing",
            "candidate_count": 1,
            "candidate_event_id": candidate_id,
        }

    return {
        "prediction_status": "single_candidate",
        "candidate_count": 1,
        "responsible_agent": action["agent_id"],
        "responsible_step": action["step_id"],
        "responsible_action_event_id": action["event_id"],
        "responsible_edge": {"from_event_id": parent["event_id"], "to_event_id": candidate_id},
        "evidence": {
            "candidate_event_id": candidate_id,
            "candidate_basis": candidate_info["basis"],
            "mismatched_fields": candidate_info.get("mismatched_fields", []),
        },
    }


def score(prediction: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    """Compare an already-frozen prediction with labels; never changes prediction."""
    abstained = prediction.get("prediction_status") != "single_candidate"
    predicted_edge = prediction.get("responsible_edge")
    truth_edge = truth.get("responsible_edge")
    truth_action_id = truth.get("responsible_action_event_id")
    return {
        "abstained": abstained,
        "agent_exact_match": (not abstained) and prediction.get("responsible_agent") == truth.get("responsible_agent"),
        "step_exact_match": (not abstained) and prediction.get("responsible_step") == truth.get("responsible_step"),
        "action_exact_match": None if truth_action_id is None else ((not abstained) and prediction.get("responsible_action_event_id") == truth_action_id),
        "edge_exact_match": (not abstained) and predicted_edge == truth_edge,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _write_new(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    predict_parser = commands.add_parser("predict", help="predict from trace only")
    predict_parser.add_argument("--trace", type=Path, required=True)
    predict_parser.add_argument("--output", type=Path, required=True)
    score_parser = commands.add_parser("score", help="score a frozen prediction against ground truth")
    score_parser.add_argument("--prediction", type=Path, required=True)
    score_parser.add_argument("--truth", type=Path, required=True)
    score_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "predict":
        trace = _read_jsonl(args.trace)
        prediction = predict(trace)
        prediction["run_id"] = trace[0].get("run_id") if trace else None
        _write_new(args.output, prediction)
        print(json.dumps(prediction, ensure_ascii=False, indent=2))
        return 0

    prediction = json.loads(args.prediction.read_text(encoding="utf-8"))
    truth = json.loads(args.truth.read_text(encoding="utf-8"))
    if prediction.get("run_id") != truth.get("run_id"):
        parser.error("prediction and truth run_id do not match")
    result = {
        "run_id": prediction.get("run_id"),
        "prediction_file": str(args.prediction),
        "truth_file": str(args.truth),
        "scores": score(prediction, truth),
        "claim_status": "SYNTHETIC_PROTOCOL_CHECK_ONLY",
    }
    _write_new(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
