#!/usr/bin/env python3
"""Run one bounded real two-agent failure scenario; no automatic retries."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import time

from capture_real_application import capture_agent, save, stop


SCENARIOS = {
    "error-propagation-v1": {
        "ground_truth": {"fault_type": "error_propagation", "responsible_agent": "agent_a",
                         "responsible_step": "agent_a.bash_1",
                         "responsible_edge": {"from": "agent_a.bash_1", "to": "agent_a.write_1"},
                         "propagation_edge": {"from": "agent_a.write_1", "to": "agent_b.bash_1"},
                         "oracle": {"actual_status": "down", "expected_action": "RESTART"}},
        "agent_a": ("Bash,Write", "Use Bash exactly once to run python3 \"{root}/scenario_service_observer.py\". Treat its complete JSON as the observation. Then use Write exactly once to create handoff.json containing service and reported_status from that actual output. Do not repair or hide inconsistent fields. Finish briefly."),
        "agent_b": ("Bash,Write", "Use Bash exactly once to run python3 \"{root}/scenario_service_decider.py\" handoff.json. Treat its JSON as the downstream decision. Then use Write exactly once to create decision.json with exactly service, observed_status and action from that output. Finish briefly."),
    },
    "routing-error-v1": {
        "ground_truth": {"fault_type": "routing_role_error", "responsible_agent": "agent_a",
                         "responsible_step": "agent_a.bash_1",
                         "responsible_edge": {"from": "agent_a.bash_1", "to": "agent_a.write_1"},
                         "propagation_edge": {"from": "agent_a.write_1", "to": "agent_b.bash_1"},
                         "oracle": {"required_role": "retrieval_specialist", "expected_retrieved": True}},
        "agent_a": ("Bash,Write", "Use Bash exactly once to run python3 \"{root}/scenario_faulty_router.py\". Treat its complete JSON as the router output. Then use Write exactly once to create route.json containing task, required_capability, selected_role, selected_capabilities and route_valid from that actual output. Do not change the selected role. Finish briefly."),
        "agent_b": ("Bash,Write", "Use Bash exactly once to run python3 \"{root}/scenario_route_executor.py\" route.json. Treat its JSON as the execution result. Then use Write exactly once to create result.json with exactly task, executed_role, retrieved and answer from that output. Finish briefly."),
    },
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scenario", choices=tuple(SCENARIOS), required=True)
    parser.add_argument("--per-session-budget", type=float, default=0.13)
    args = parser.parse_args()
    if args.per_session_budget <= 0 or args.per_session_budget > 0.13:
        parser.error("Scenario gate allows at most 0.13 USD per CLI session")
    if os.geteuid() != 0:
        parser.error("Run as root in the known Ubuntu WSL distribution")
    if not (os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")):
        parser.error("Missing existing credential")
    from urllib.parse import urlparse
    host = urlparse(os.environ.get("ANTHROPIC_BASE_URL", "https://api.deepseek.com")).hostname
    socket.getaddrinfo(host, 443)
    if not Path("/sys/kernel/tracing/events/sched/sched_process_exec").exists():
        subprocess.run(["mount", "-t", "tracefs", "tracefs", "/sys/kernel/tracing"], check=True)
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False); (output / "workspace").mkdir()
    os.environ["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    spec = SCENARIOS[args.scenario]; root = Path(__file__).resolve().parent
    truth = {"schema_version": "agentops-ground-truth-v0.3", "created_before_api": True,
             "semantic_step_rule": "{agent_id}.{lowercase_tool_name}_{one_based_ordinal_within_agent_tool_name}",
             "excluded_from_alignment": True, **spec["ground_truth"]}
    save(output / "ground_truth.json", truth)
    scope = {"schema_version": "agentops-observation-scope-v0.1", "run_id": output.name,
             "evidence_kind": "runtime_observed", "host_id": hashlib.sha256(Path("/etc/machine-id").read_bytes()).hexdigest(),
             "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
             "pid_namespace": os.readlink("/proc/self/ns/pid"), "clock_domain": "linux-CLOCK_REALTIME-ms",
             "uncertainty_ms": 1, "clock_boundary": "Launcher wall clock; AgentSight conversion evaluated separately"}
    save(output / "capture-scope.json", scope)
    save(output / "plan.json", {"run_id": output.name, "scenario": args.scenario, "planned_cli_sessions": 2,
                                "per_session_budget_usd": args.per_session_budget,
                                "planned_batch_budget_usd": 2 * args.per_session_budget,
                                "authorization": "User asked to continue the complete real experiments",
                                "no_automatic_retry": True})
    save(output / "versions.json", {name: subprocess.run([name, "--version"], capture_output=True, text=True).stdout.strip()
                                      for name in ("claude", "agentsight", "python3")})
    db = output / "session.db"
    record_log, stream_log = (output / "record.log").open("x"), (output / "raw-stream.log").open("x")
    observer = subprocess.Popen(["agentsight", "record", "-c", "claude", "--db", str(db), "--no-server"],
                                stdout=record_log, stderr=subprocess.STDOUT, start_new_session=True)
    debug = None; summaries = []
    try:
        time.sleep(2)
        if observer.poll() is not None: raise RuntimeError("AgentSight exited before API invocation")
        debug = subprocess.Popen(["agentsight", "debug", "process"], stdout=stream_log,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        time.sleep(1)
        if debug.poll() is not None: raise RuntimeError("Process observer exited before API invocation")
        tools_a, prompt_a = spec["agent_a"]; tools_b, prompt_b = spec["agent_b"]
        summaries.append(capture_agent(output, "agent_a", prompt_a.format(root=root), tools_a, args.per_session_budget, scope))
        if summaries[-1]["success"] and observer.poll() is None:
            summaries.append(capture_agent(output, "agent_b", prompt_b.format(root=root), tools_b, args.per_session_budget, scope))
        time.sleep(2)
    finally:
        stop(observer)
        if debug is not None: stop(debug)
        record_log.close(); stream_log.close()
        save(output / "capture-summary.json", {"agents": summaries,
             "reported_cost_usd": sum(s["reported_cost_usd"] or 0 for s in summaries),
             "cost_complete": bool(summaries) and all(s["reported_cost_usd"] is not None for s in summaries),
             "actual_cli_sessions": len(summaries), "scenario": args.scenario})
    counts = {}
    if db.exists():
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as connection:
            for (table,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table'"):
                counts[table] = connection.execute('SELECT count(*) FROM "' + table.replace('"','""') + '"').fetchone()[0]
    save(output / "observation-counts.json", counts)
    print(json.dumps({"run_id": output.name, "scenario": args.scenario,
                      "agents": [{k: s[k] for k in ("agent_id", "success", "reported_cost_usd", "stream_lines")} for s in summaries],
                      "table_counts": counts}))
    return 0 if len(summaries) == 2 and all(s["success"] for s in summaries) and counts.get("tool_calls", 0) else 2


if __name__ == "__main__":
    raise SystemExit(main())
