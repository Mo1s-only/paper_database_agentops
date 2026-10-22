#!/usr/bin/env python3
"""Post-prediction repair/control validation with a task-label-blind oracle."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


def evaluate_contract(trace: list[dict[str, Any]]) -> bool:
    """Evaluate success from the task's declared contract, not task/fault labels."""
    starts = [event for event in trace if event.get("event_type") == "task.start"]
    if len(starts) != 1 or not isinstance(starts[0].get("output_summary"), dict):
        return False
    contract = starts[0]["output_summary"]
    expected = {
        key.removeprefix("required_") if key.startswith("required_") else key: value
        for key, value in contract.items()
    }

    routes = [event for event in trace if event.get("event_type") == "route.decision"]
    if routes:
        if len(routes) != 1:
            return False
        route = routes[0]
        required_role = route.get("input_summary", {}).get("required_role", expected.get("role"))
        assigned_role = route.get("output_summary", {}).get("assigned_role")
        return required_role is not None and assigned_role == required_role

    results = [event for event in trace if event.get("event_type") == "tool.result"]
    if len(results) != 1 or results[0].get("status") != "success":
        return False
    output = results[0].get("output_summary")
    if not isinstance(output, dict) or not expected:
        return False
    comparable = [key for key in expected if key in output]
    return bool(comparable) and all(output[key] == expected[key] for key in comparable)


def validate_counterfactual(
    trace: list[dict[str, Any]], prediction: dict[str, Any], plan: dict[str, Any]
) -> dict[str, Any]:
    trace_run_ids = {event.get("run_id") for event in trace if event.get("run_id") is not None}
    if len(trace_run_ids) > 1 or (trace_run_ids and prediction.get("run_id") not in trace_run_ids):
        return {"status": "not_tested", "reason": "prediction_trace_run_id_mismatch"}
    if prediction.get("run_id") != plan.get("run_id"):
        return {"status": "not_tested", "reason": "prediction_plan_run_id_mismatch"}
    if prediction.get("prediction_status") != "single_candidate":
        return {"status": "not_tested", "reason": "prediction_abstained"}
    candidate_id = prediction.get("evidence", {}).get("candidate_event_id")
    target_id = plan.get("repair", {}).get("event_id")
    if not candidate_id or candidate_id != target_id:
        return {"status": "not_tested", "reason": "prediction_does_not_select_planned_repair_target"}

    repaired = copy.deepcopy(trace)
    target = next((event for event in repaired if event.get("event_id") == target_id), None)
    if target is None:
        return {"status": "not_tested", "reason": "repair_target_missing"}
    patch = plan["repair"]
    target["status"] = patch.get("status", target.get("status"))
    target["output_summary"] = dict(patch.get("output_summary", {}))
    repaired_success = evaluate_contract(repaired)

    control = copy.deepcopy(trace)
    control_plan = plan.get("control", {})
    control_target = next((event for event in control if event.get("event_id") == control_plan.get("event_id")), None)
    if control_target is None:
        return {"status": "not_tested", "reason": "control_target_missing", "repaired_success": repaired_success}
    control_target.setdefault("attributes", {})["unrelated_intervention"] = True
    control_success = evaluate_contract(control)
    return {
        "status": "evaluated",
        "repair_target_event_id": target_id,
        "control_target_event_id": control_plan.get("event_id"),
        "repaired_success": repaired_success,
        "control_success": control_success,
        "counterfactual_flip": repaired_success and not control_success,
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
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--prediction", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    trace = _read_jsonl(args.trace)
    prediction = json.loads(args.prediction.read_text(encoding="utf-8"))
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    result = validate_counterfactual(trace, prediction, plan)
    result.update({"run_id": prediction.get("run_id"), "claim_status": "SYNTHETIC_PROTOCOL_CHECK_ONLY"})
    _write_new(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
