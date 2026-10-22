#!/usr/bin/env python3
"""One bounded real-API AgentSight/eBPF canary, with no automatic retry."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time
from urllib.parse import urlparse

from analyze_ebpf_real_canary import analyze as analyze_real_canary
from capture_real_application import capture_agent, save, stop


REPO = Path(__file__).resolve().parents[2]
BASELINE = REPO / "my_paper_coding/experiment_control/cost-ledger-20261012-sse-clock.json"
MANIFEST = REPO / "my_paper_coding/experiment_control/real-api-error-agentrx-20261019.json"
PREVIOUS_SCENARIO = REPO / "lab/experiment/experiment_20261019_18/results/run-dff396441f6a/error-propagation/capture-summary.json"
PREVIOUS_AGENTRX = REPO / "lab/experiment/experiment_20261019_18/results/run-dff396441f6a/agentrx-tau12/cli-stdout.json"
DEFAULT_MAX_SESSION_USD = 0.05
DEEPSEEK_ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic"


def configure_deepseek_environment(environ: dict | None = None) -> bool:
    """Map a DeepSeek-specific key to Claude Code's expected Anthropic variable names.

    Values are kept in process memory only; callers must never serialize or print
    this environment mapping.
    """
    env = os.environ if environ is None else environ
    if not (env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY")):
        deepseek_key = env.get("DEEPSEEK_API_KEY")
        if deepseek_key:
            env["ANTHROPIC_AUTH_TOKEN"] = deepseek_key
    env.setdefault("ANTHROPIC_BASE_URL", DEEPSEEK_ANTHROPIC_BASE_URL)
    return bool(env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY"))


def preflight_failure_code(error: Exception) -> str:
    """Return a safe, stable category without persisting exception details."""
    message = str(error).lower()
    if "credential" in message:
        return "credential_missing"
    if "upper bound" in message or "hard stop" in message or "2 cny" in message:
        return "budget_guard_blocked"
    if "provider url" in message:
        return "provider_guard_blocked"
    if "root required" in message:
        return "privilege_guard_blocked"
    return "preflight_failed"


def cumulative_budget_exceeded(
    projected_total: float,
    hard_stop: float,
    conservative_cny: float,
    batch_cap_cny: float,
    ignore_cumulative_budget: bool = False,
) -> bool:
    if ignore_cumulative_budget:
        return False
    return projected_total > hard_stop + 1e-9 or conservative_cny > batch_cap_cny + 1e-9


def preflight(output: Path, max_session_usd: float, ignore_cumulative_budget: bool = False) -> dict:
    configure_deepseek_environment()
    if not 0 < max_session_usd <= DEFAULT_MAX_SESSION_USD:
        raise ValueError("Session ceiling must be in (0, 0.05] USD")
    ledger = json.loads(BASELINE.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    scenario = json.loads(PREVIOUS_SCENARIO.read_text(encoding="utf-8"))
    agentrx = json.loads(PREVIOUS_AGENTRX.read_text(encoding="utf-8"))
    baseline = float(ledger["total_cost_usd"])
    assert abs(baseline - float(manifest["baseline_ledger_total_usd"])) < 1e-9
    assert manifest["historical_ledger_override"]["approved_by_user"] is True
    assert scenario["cost_complete"] is True
    assert scenario["actual_cli_sessions"] == 2
    assert agentrx["is_error"] is False
    previous = float(scenario["reported_cost_usd"]) + float(agentrx["total_cost_usd"])
    previous_canaries = []
    for summary_path in sorted(output.parent.glob("real-canary-*/diagnostic-summary.json")):
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("real_api") is not True or summary.get("cost_status") not in {
            "within_session_limit", "exceeded_session_limit"
        }:
            raise RuntimeError(f"Prior real canary cost is not verified: {summary_path}")
        cost = summary["cli"].get("reported_cost_usd")
        if cost is None or float(cost) < 0:
            raise RuntimeError(f"Prior real canary has no valid reported cost: {summary_path}")
        previous_canaries.append({"run": summary_path.parent.name, "reported_cost_usd": float(cost),
                                  "cost_status": summary["cost_status"]})
    previous_canary_usd = sum(item["reported_cost_usd"] for item in previous_canaries)
    hard_stop = float(manifest["hard_stop_total_usd"])
    batch_cap_cny = float(manifest.get("batch_cap_cny", 2.0))
    projected_total = baseline + previous + previous_canary_usd + max_session_usd
    conservative_cny = (previous + previous_canary_usd + max_session_usd) * float(manifest["planning_usd_cny_rate"])
    if cumulative_budget_exceeded(
        projected_total, hard_stop, conservative_cny, batch_cap_cny, ignore_cumulative_budget
    ):
        raise RuntimeError("The one-session upper bound exceeds the authorized hard stop or batch cap")
    if os.geteuid() != 0:
        raise RuntimeError("Ubuntu root required for eBPF")
    if not (os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")):
        raise RuntimeError("DeepSeek credential missing (set DEEPSEEK_API_KEY or Claude Code's ANTHROPIC_AUTH_TOKEN)")
    url = urlparse(os.environ.get("ANTHROPIC_BASE_URL", ""))
    if (url.scheme, url.hostname, url.path.rstrip("/")) != ("https", "api.deepseek.com", "/anthropic"):
        raise RuntimeError("Unexpected provider URL; refusing real API call")
    if not Path("/sys/kernel/tracing/events/sched/sched_process_exec").exists():
        subprocess.run(["mount", "-t", "tracefs", "tracefs", "/sys/kernel/tracing"], check=True)
    return {
        "historical_baseline_usd": baseline,
        "historical_raw_logs_fully_verified": False,
        "previous_scenario_usd": float(scenario["reported_cost_usd"]),
        "previous_agentrx_usd": float(agentrx["total_cost_usd"]),
        "previous_incremental_usd": previous,
        "previous_canaries": previous_canaries,
        "previous_canary_usd": previous_canary_usd,
        "this_session_max_usd": max_session_usd,
        "projected_cumulative_usd": round(projected_total, 7),
        "hard_stop_usd": hard_stop,
        "authorized_batch_cap_cny": batch_cap_cny,
        "projected_incremental_cny_at_planning_rate": round(conservative_cny, 6),
        "planning_rate_cny_per_usd": float(manifest["planning_usd_cny_rate"]),
        "cumulative_budget_enforced": not ignore_cumulative_budget,
        "cumulative_budget_override": (
            "User explicitly requested to proceed regardless of cumulative budget on 2026-10-21"
            if ignore_cumulative_budget else None
        ),
        "no_automatic_retry": True,
    }


def summarize_db(path: Path, cli_pid: int) -> dict:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts = {table: connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
                  for table in ("llm_calls", "tool_calls", "token_usage", "network_targets", "process_nodes", "audit_events")
                  if table in tables}
        audit_types = dict(connection.execute("SELECT audit_type,count(*) FROM audit_events GROUP BY audit_type"))
        pid_rows = connection.execute("SELECT count(*) FROM process_nodes WHERE pid=?", (cli_pid,)).fetchone()[0]
        hosts = [row[0] for row in connection.execute("SELECT DISTINCT host FROM network_targets ORDER BY host")]
    return {"counts": counts, "audit_types": audit_types, "cli_pid_process_rows": pid_rows,
            "network_hosts": hosts,
            "ebpf_system_data_present": counts.get("process_nodes", 0) > 0 and audit_types.get("process", 0) > 0,
            "llm_semantics_present": counts.get("llm_calls", 0) > 0,
            "tool_semantics_present": counts.get("tool_calls", 0) > 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--agentsight-bin", default="agentsight", help="Collector to test without replacing the installed binary")
    parser.add_argument("--max-session-usd", type=float, default=DEFAULT_MAX_SESSION_USD)
    parser.add_argument(
        "--ignore-cumulative-budget", action="store_true",
        help="Record an explicit user override of cumulative budget checks; per-session soft limit still applies",
    )
    parser.add_argument("--preflight-only", action="store_true", help="Check budget and runtime prerequisites without starting an API session")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error(f"Refusing to overwrite existing experiment: {output}")
    try:
        budget = preflight(output, args.max_session_usd, args.ignore_cumulative_budget)
    except Exception as error:
        # Keep a durable, secret-free record of runs stopped before any API call.
        # A timestamped sibling file leaves the requested run directory available
        # for a later retry after credentials or environment are repaired.
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        failure_path = output.with_name(f"{output.name}-preflight-{timestamp}.json")
        save(failure_path, {
            "schema_version": "agentops-real-api-preflight-v0.1",
            "run_name": output.name,
            "status": "blocked_before_api",
            "reason_code": preflight_failure_code(error),
            "exception_type": type(error).__name__,
            "api_request_sent": False,
            "reported_cost_usd": 0,
            "automatic_retries": 0,
            "secret_values_recorded": False,
        })
        raise
    if args.preflight_only:
        print(json.dumps({"preflight": "PASS", "api_request_sent": False, "budget": budget}, ensure_ascii=False))
        return 0
    agentsight_bin = args.agentsight_bin
    agentsight_path = Path(agentsight_bin).resolve(strict=True)
    agentsight_sha256 = hashlib.sha256(agentsight_path.read_bytes()).hexdigest()
    output.mkdir(parents=True)
    (output / "workspace").mkdir()
    save(output / "budget-preflight.json", budget)
    scope = {
        "schema_version": "agentops-observation-scope-v0.1", "run_id": output.name,
        "host_id": hashlib.sha256(Path("/etc/machine-id").read_bytes()).hexdigest(),
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "pid_namespace": os.readlink("/proc/self/ns/pid"), "clock_domain": "linux-CLOCK_REALTIME-ms",
        "uncertainty_ms": 1,
    }
    save(output / "capture-scope.json", scope)
    versions = {
        name: subprocess.run([binary, "--version"], capture_output=True, text=True).stdout.strip()
        for name, binary in (("claude", "claude"), ("agentsight", str(agentsight_path)), ("python3", "python3"))
    }
    versions["agentsight_binary"] = {"path": str(agentsight_path), "sha256": agentsight_sha256}
    save(output / "versions.json", versions)
    os.environ["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    db = output / "session.db"
    recorder = None
    debug = None
    result = None
    with (output / "record.log").open("xb") as record_log, (output / "raw-process.log").open("xb") as raw_log:
        try:
            recorder = subprocess.Popen([agentsight_bin, "record", "-c", "claude", "--db", str(db), "--no-server"],
                                        cwd=output, stdout=record_log, stderr=subprocess.STDOUT,
                                        start_new_session=True)
            time.sleep(4)
            if recorder.poll() is not None:
                raise RuntimeError("AgentSight recorder exited before the real CLI")
            debug = subprocess.Popen([agentsight_bin, "debug", "process"], cwd=output,
                                     stdout=raw_log, stderr=subprocess.STDOUT, start_new_session=True)
            time.sleep(2)
            if debug.poll() is not None:
                raise RuntimeError("eBPF process observer exited before the real CLI")
            prompt = (
                "Use Bash exactly once to run this compound command: python3 \""
                + str(Path(__file__).with_name("scenario_service_observer.py"))
                + "\" && python3 \""
                + str(Path(__file__).with_name("scenario_service_observer.py"))
                + "\" && /bin/true. Read the first Python JSON and report only its service and reported_status. "
                  "Do not use any other tool."
            )
            result = capture_agent(
                output, "agent_a", prompt, "Bash", args.max_session_usd, scope,
                tool_id_bridge_events=output / "tool-call-hook-events.jsonl",
            )
            time.sleep(2)
        finally:
            if recorder is not None:
                stop(recorder)
            if debug is not None:
                stop(debug)
    if result is None:
        raise RuntimeError("No CLI result; no automatic retry")
    observed = summarize_db(db, result["pid"])
    actual_cost = result["reported_cost_usd"]
    post_analysis = analyze_real_canary(output)
    save(output / "diagnostic-summary.json", {
        "authorization": "User explicitly requested a real API AgentSight/eBPF diagnostic and cumulative-budget override on 2026-10-21",
        "real_api": True, "sessions": 1, "automatic_retries": 0,
        "cli": {key: result[key] for key in ("agent_id", "pid", "exit_code", "timed_out", "success", "reported_cost_usd")},
        "budget": budget,
        "observed": observed,
        "post_analysis": post_analysis["verified"],
        "cost_status": ("missing" if actual_cost is None else
                        "within_session_limit" if actual_cost <= args.max_session_usd else
                        "exceeded_session_limit"),
        "interpretation": "Process/file/network eBPF evidence is separate from parsed LLM/tool semantic tables.",
    })
    print(json.dumps({"success": result["success"], "cost_usd": actual_cost, "observed": observed}, ensure_ascii=False))
    return 0 if result["success"] and observed["ebpf_system_data_present"] and actual_cost is not None and actual_cost <= args.max_session_usd else 2


if __name__ == "__main__":
    raise SystemExit(main())
