#!/usr/bin/env python3
"""Predict a failure location from native evidence, then reveal frozen truth for scoring."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

from align_candidates import sha256


def write_new_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def decode_result(content):
    if isinstance(content, dict):
        return content
    if isinstance(content, list):
        text = "".join(str(block.get("text", "")) if isinstance(block, dict) else str(block)
                       for block in content)
    else:
        text = str(content)
    try:
        value = json.loads(text.strip())
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def native_tools(run: Path) -> list[dict]:
    tools = []
    for agent in ("agent_a", "agent_b"):
        counters = Counter()
        by_id = {}
        path = run / f"claude-agent-{agent[-1]}.log"
        for line_no, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            row = json.loads(text)
            content = row.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if block.get("type") == "tool_use":
                    name = str(block.get("name", "unknown")).lower()
                    name = re.sub(r"[^a-z0-9]+", "_", name).strip("_") or "unknown"
                    counters[name] += 1
                    item = {"agent_id": agent, "tool_call_id": block["id"], "tool_name": block.get("name"),
                            "semantic_step_id": f"{agent}.{name}_{counters[name]}",
                            "tool_use_ref": f"{path.as_posix()}#line={line_no}", "result": None,
                            "tool_result_ref": None}
                    tools.append(item); by_id[block["id"]] = item
                elif block.get("type") == "tool_result" and block.get("tool_use_id") in by_id:
                    item = by_id[block["tool_use_id"]]
                    item["result"] = decode_result(block.get("content"))
                    item["tool_result_ref"] = f"{path.as_posix()}#line={line_no}"
    return tools


def alignment_by_tool(run: Path) -> dict[str, dict]:
    candidates = [
        run / "alignment-session-and-tool" / "application-alignments.jsonl",
        run / "alignment-inputs" / "alignment-session-and-tool" / "application-alignments.jsonl",
        *(folder / "alignment-session-and-tool" / "application-alignments.jsonl"
          for folder in sorted(run.glob("alignment-inputs-*"))),
    ]
    path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return {row["tool_call_id"]: {"status": row["status"], "target_ref": row.get("target_ref")}
            for row in rows}


def predict(run: Path) -> dict:
    tools = native_tools(run)
    anomalies = []
    for item in tools:
        result = item["result"]
        if not isinstance(result, dict):
            continue
        if result.get("consistent") is False:
            anomalies.append((item, "error_propagation"))
        if result.get("route_valid") is False:
            anomalies.append((item, "routing_role_error"))
    if len(anomalies) != 1:
        raise ValueError(f"Expected one observable anomaly, found {len(anomalies)}")
    culprit, fault_type = anomalies[0]
    own = [item for item in tools if item["agent_id"] == culprit["agent_id"]]
    position = own.index(culprit)
    next_own = own[position + 1] if position + 1 < len(own) else None
    agents = list(dict.fromkeys(item["agent_id"] for item in tools))
    agent_position = agents.index(culprit["agent_id"])
    next_agent = agents[agent_position + 1] if agent_position + 1 < len(agents) else None
    next_agent_first = next((item for item in tools if item["agent_id"] == next_agent), None)
    alignments = alignment_by_tool(run)
    workspace = run / "workspace"
    if fault_type == "error_propagation":
        decision = json.loads((workspace / "decision.json").read_text(encoding="utf-8"))
        actual = culprit["result"].get("raw_probe_status")
        expected = "RESTART" if actual == "down" else "NO_RESTART"
        outcome = {"failed": decision.get("action") != expected, "actual_status": actual,
                   "observed_action": decision.get("action"), "expected_action_from_rule": expected}
    else:
        result = json.loads((workspace / "result.json").read_text(encoding="utf-8"))
        route = culprit["result"]
        outcome = {"failed": route.get("route_valid") is False and result.get("retrieved") is not True,
                   "required_capability": route.get("required_capability"),
                   "selected_role": route.get("selected_role"), "observed_retrieved": result.get("retrieved")}
    return {
        "schema_version": "agentops-scenario-prediction-v0.1", "run_id": run.name,
        "prediction_inputs": [f"claude-agent-{suffix}.log" for suffix in ("a", "b")] +
                             ["workspace", "alignment-session-and-tool/application-alignments.jsonl"],
        "ground_truth_used": False, "semantic_step_rule":
        "{agent_id}.{lowercase_tool_name}_{one_based_ordinal_within_agent_tool_name}",
        "semantic_step_map": [{k: item[k] for k in ("agent_id", "tool_call_id", "tool_name", "semantic_step_id",
                                                       "tool_use_ref", "tool_result_ref")} |
                              {"system_alignment": alignments.get(item["tool_call_id"], {"status": "missing"})}
                              for item in tools],
        "fault_type": fault_type, "responsible_agent": culprit["agent_id"],
        "responsible_step": culprit["semantic_step_id"],
        "responsible_edge": {"from": culprit["semantic_step_id"],
                             "to": next_own["semantic_step_id"] if next_own else None},
        "propagation_edge": {"from": next_own["semantic_step_id"] if next_own else culprit["semantic_step_id"],
                             "to": next_agent_first["semantic_step_id"] if next_agent_first else None},
        "trigger_observation": culprit["result"],
        "responsible_step_system_alignment": alignments.get(culprit["tool_call_id"], {"status": "missing"}),
        "task_outcome": outcome,
        "boundary": "Deterministic scenario rule over native tool results; one controlled run, not a calibrated general classifier",
    }


def score(prediction: dict, truth: dict) -> dict:
    fields = ("fault_type", "responsible_agent", "responsible_step", "responsible_edge", "propagation_edge")
    exact = {f"{field}_exact": prediction.get(field) == truth.get(field) for field in fields}
    return {"schema_version": "agentops-scenario-score-v0.1", **exact,
            "all_attribution_fields_exact": all(exact.values()),
            "task_failure_observed": prediction["task_outcome"]["failed"],
            "scope": "Exact-match score against ground truth frozen before API invocation; n=1 for this scenario"}


def capture_gate(alignment: dict) -> dict:
    statuses = alignment["identity_modes"]["session-and-tool"]
    accepted = statuses.get("accepted", 0)
    complete = (alignment["native_tool_starts"] == alignment["system_tool_ids"] == accepted
                and not alignment.get("missing_ids"))
    return {"capture_status": "complete" if complete else "incomplete",
            "system_edge_claim_allowed": complete,
            "reason": None if complete else "native and AgentSight tool coverage is not one-to-one"}


def validate(run: Path) -> dict:
    prediction_path = run / "scenario-prediction.json"
    prediction = predict(run)
    # This exclusive write occurs before the validator artifact is opened below.
    write_new_json(prediction_path, prediction)
    truth_path = run / "ground_truth.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    scored = score(prediction, truth)
    scored.update(prediction_sha256=sha256(prediction_path), ground_truth_sha256=sha256(truth_path),
                  truth_created_before_api=truth.get("created_before_api"),
                  truth_excluded_from_alignment=truth.get("excluded_from_alignment"))
    write_new_json(run / "scenario-score.json", scored)
    alignment_candidates = [run / "real-alignment-comparison.json",
                            run / "alignment-inputs" / "real-alignment-comparison.json",
                            *(folder / "real-alignment-comparison.json"
                              for folder in sorted(run.glob("alignment-inputs-*")))]
    alignment_path = next((candidate for candidate in alignment_candidates if candidate.exists()),
                          alignment_candidates[0])
    alignment = json.loads(alignment_path.read_text(encoding="utf-8"))
    capture = json.loads((run / "capture-summary.json").read_text(encoding="utf-8"))
    gate = capture_gate(alignment)
    report = {"run_id": run.name, "scenario": capture["scenario"], "api_sessions": capture["actual_cli_sessions"],
              "reported_cost_usd": capture["reported_cost_usd"],
              "native_tool_starts": alignment["native_tool_starts"],
              "agentsight_tool_records": alignment["system_tool_ids"],
              "session_and_tool_status": alignment["identity_modes"]["session-and-tool"],
              **gate,
              "prediction": {k: prediction[k] for k in ("fault_type", "responsible_agent", "responsible_step",
                                                          "responsible_edge", "propagation_edge", "task_outcome",
                                                          "responsible_step_system_alignment")},
              "score": scored, "evidence_status": "VERIFIED_CONTROLLED_RUN",
              "generalization_status": "UNVERIFIED"}
    write_new_json(run / "scenario-validation-report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.run), ensure_ascii=False))
