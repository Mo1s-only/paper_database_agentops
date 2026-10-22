#!/usr/bin/env python3
"""Run one budgeted AgentRx trajectory diagnosis after a real error-propagation run.

The input is an official public example trajectory, not a replay of the Tau Retail
environment and not a paired AgentSight system trace. No API is called without
--execute. Ground truth is opened only after the model prediction is saved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess


REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "lab/AgentRx/trajectories/tau-retail/instruction_adherence_failure.json"
TRUTH = REPO / "lab/AgentRx/data/ground_truth/tau_retail.json"
MANIFEST = REPO / "my_paper_coding/experiment_control/real-api-error-agentrx-20261019.json"
LEDGER = REPO / "my_paper_coding/experiment_control/cost-ledger-20261012-sse-clock.json"
SOURCE_SHA256 = "8c6579ed82d379012118d2aa8b9fc82a95b004d89ecd76a9890081721acf1137"
TRUTH_SHA256 = "a0e6fa3b7a8889f6728562c38ca6f708ecf6300806ccebd86639ad901c1f61e9"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_prompt(source: dict) -> str:
    if source.get("task_id") != 12 or not isinstance(source.get("traj"), list):
        raise ValueError("unexpected AgentRx example structure")
    # The source's info/reward fields contain task oracle material. Only traj is
    # sent to the model; the independent root-cause labels are never included.
    payload = {"task_id": 12, "trajectory": source["traj"]}
    return (
        "Read this failed AgentRx execution trajectory. Identify the earliest "
        "decisive failure supported by visible steps. Return only JSON with "
        "step_number (integer or null), failed_agent (string or null), "
        "failure_category (string or null), and reason (one short sentence). "
        "Use the step index in the trajectory. Do not use tools or external data.\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def check_budget(manifest: dict, ledger: dict, error_summary: dict,
                 error_plan: dict) -> dict:
    baseline = float(manifest["baseline_ledger_total_usd"])
    if abs(float(ledger["total_cost_usd"]) - baseline) > 0.000001:
        raise ValueError("cumulative ledger differs from frozen baseline; refresh batch plan")
    if error_plan.get("scenario") != "error-propagation-v1":
        raise ValueError("the preceding run is not error-propagation-v1")
    if float(error_plan.get("per_session_budget_usd", 1)) > float(
            manifest["error_propagation_max_usd_per_session"]):
        raise ValueError("preceding per-session budget exceeded allocation")
    if not error_summary.get("cost_complete") or error_summary.get("actual_cli_sessions") != 2:
        raise ValueError("preceding run lacks two complete cost records")
    agents = error_summary.get("agents", [])
    if len(agents) != 2 or not all(agent.get("success") for agent in agents):
        raise ValueError("preceding run did not complete successfully")
    error_cost = float(error_summary["reported_cost_usd"])
    probe_cap = float(manifest["agentrx_max_usd"])
    rate = float(manifest["planning_usd_cny_rate"])
    cap_cny = float(manifest["batch_cap_cny"])
    planned_total_usd = error_cost + probe_cap
    if error_cost < 0 or probe_cap <= 0 or planned_total_usd * rate >= cap_cny:
        raise ValueError("combined planned CLI cost would reach or exceed 2 CNY")
    if baseline + planned_total_usd > float(manifest["hard_stop_total_usd"]) + 1e-9:
        raise ValueError("cumulative batch hard stop would be exceeded")
    return {"error_reported_usd": error_cost, "probe_cap_usd": probe_cap,
            "planned_total_usd": planned_total_usd,
            "planned_total_cny_at_rate": planned_total_usd * rate,
            "planning_usd_cny_rate": rate, "batch_cap_cny": cap_cny}


def reported_cost_status(cost, cap_usd: float) -> str:
    if not isinstance(cost, (int, float)) or isinstance(cost, bool):
        return "unknown"
    return "within_cap" if float(cost) <= cap_usd else "exceeded_cap"


def save_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="make one real Claude CLI API call")
    parser.add_argument("--output", type=Path, help="new ignored run directory")
    parser.add_argument("--error-run", type=Path, help="completed error-propagation run directory")
    parser.add_argument("--cumulative-manifest", type=Path, default=MANIFEST,
                        help="budget manifest for this API batch")
    parser.add_argument("--cumulative-ledger", type=Path, default=LEDGER,
                        help="ledger snapshot used by this API batch")
    args = parser.parse_args()

    if sha256(SOURCE) != SOURCE_SHA256 or sha256(TRUTH) != TRUTH_SHA256:
        parser.error("AgentRx source or independent labels changed from the frozen files")
    source = read_json(SOURCE)
    prompt = build_prompt(source)
    source_summary = {"source": str(SOURCE), "source_sha256": SOURCE_SHA256,
                      "truth_sha256": TRUTH_SHA256, "task_id": 12,
                      "trajectory_steps": len(source["traj"]),
                      "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                      "prompt_characters": len(prompt), "api_calls_made": 0}
    if not args.execute:
        print(json.dumps(source_summary, ensure_ascii=False))
        return 0

    if args.output is None or args.error_run is None:
        parser.error("--execute requires --output and --error-run")
    output = args.output.resolve()
    if output.exists():
        parser.error(f"refusing to overwrite: {output}")
    manifest = read_json(args.cumulative_manifest)
    budget = check_budget(manifest, read_json(args.cumulative_ledger),
                          read_json(args.error_run / "capture-summary.json"),
                          read_json(args.error_run / "plan.json"))
    if not shutil.which("claude"):
        parser.error("claude CLI is unavailable")
    if not (os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")):
        parser.error("configured API credential is unavailable")

    output.mkdir(parents=True, exist_ok=False)
    save_json(output / "preflight.json", {**source_summary, "budget": budget,
                                           "api_calls_made": 0})
    (output / "model-input.txt").write_text(prompt, encoding="utf-8")
    model = os.environ.get("ANTHROPIC_MODEL", "deepseek-v4-pro")
    command = ["claude", "-p", prompt, "--output-format", "json", "--model", model,
               "--max-budget-usd", str(budget["probe_cap_usd"]),
               "--tools", "", "--allowedTools", "", "--setting-sources", "",
               "--strict-mcp-config", "--disable-slash-commands",
               "--no-session-persistence"]
    process = subprocess.Popen(command, cwd=output, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        raw_stdout, raw_stderr = process.communicate(timeout=180)
        exit_code = process.returncode
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            raw_stdout, raw_stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            raw_stdout, raw_stderr = process.communicate()
        exit_code = 124
    (output / "cli-stdout.json").write_text(raw_stdout, encoding="utf-8")
    (output / "cli-stderr.log").write_text(raw_stderr, encoding="utf-8")
    # Prediction is persisted before the label file is opened for scoring.
    response = None
    try:
        response = json.loads(raw_stdout)
    except json.JSONDecodeError:
        pass
    cost = response.get("total_cost_usd") if isinstance(response, dict) else None
    predicted = None
    if isinstance(response, dict) and isinstance(response.get("result"), str):
        try:
            predicted = json.loads(response["result"])
        except json.JSONDecodeError:
            pass
    prediction = {"model": model, "exit_code": exit_code, "reported_cost_usd": cost,
                  "prediction": predicted, "raw_result": response.get("result") if isinstance(response, dict) else None}
    save_json(output / "prediction.json", prediction)

    truth_rows = read_json(TRUTH)
    truth = next(row for row in truth_rows if row.get("trajectory_id") == 12)
    root_id = truth["root_cause"]["failure_id"]
    root = next(row for row in truth["failures"] if row["failure_id"] == root_id)
    score = {"truth_step": root["step_number"], "truth_agent": root["failed_agent"],
             "truth_category": root["failure_category"],
             "step_exact": isinstance(predicted, dict) and predicted.get("step_number") == root["step_number"],
             "agent_exact": isinstance(predicted, dict) and predicted.get("failed_agent") == root["failed_agent"],
             "category_exact": isinstance(predicted, dict) and predicted.get("failure_category") == root["failure_category"],
             "reported_total_cny_at_rate": (budget["error_reported_usd"] + float(cost)) * budget["planning_usd_cny_rate"] if isinstance(cost, (int, float)) else None,
             "cost_complete": isinstance(cost, (int, float)),
             "cost_status": reported_cost_status(cost, budget["probe_cap_usd"]),
             "reported_cost_over_cap_usd": max(0.0, float(cost) - budget["probe_cap_usd"]) if isinstance(cost, (int, float)) else None}
    save_json(output / "score.json", score)
    print(json.dumps({"output": str(output), "exit_code": exit_code,
                      "reported_cost_usd": cost, "step_exact": score["step_exact"],
                      "cost_complete": score["cost_complete"]}, ensure_ascii=False))
    return 0 if exit_code == 0 and score["cost_complete"] and score["cost_status"] == "within_cap" and score["reported_total_cny_at_rate"] < budget["batch_cap_cny"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
