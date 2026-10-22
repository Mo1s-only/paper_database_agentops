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


def append_lifecycle(path: Path, stage: str, observer, debug=None, **details) -> dict:
    """Persist non-secret observer health markers around each API session."""
    row = {
        "stage": stage,
        "wall_time_ns": time.time_ns(),
        "monotonic_ns": time.monotonic_ns(),
        "observer_pid": observer.pid if observer is not None else None,
        "observer_exit_code": observer.poll() if observer is not None else None,
        "debug_pid": debug.pid if debug is not None else None,
        "debug_exit_code": debug.poll() if debug is not None else None,
        **details,
    }
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return row


def budget_projection(per_session_usd: float, sessions: int, usd_cny_rate: float,
                      cap_cny: float) -> dict:
    projected_usd = per_session_usd * sessions
    projected_cny = projected_usd * usd_cny_rate
    return {"projected_usd": round(projected_usd, 6),
            "projected_cny": round(projected_cny, 4),
            "cap_cny": cap_cny,
            "within_cap": projected_cny <= cap_cny}


def cumulative_budget_preflight(manifest: dict, ledger: dict, planned_usd: float) -> dict:
    spent = float(ledger.get("total_cost_usd", 0))
    hard_stop = float(manifest.get("hard_stop_total_usd", 0))
    projected = spent + planned_usd
    status = "PASS" if hard_stop > 0 and projected <= hard_stop else "BLOCKED"
    return {"status": status, "already_spent_usd": round(spent, 6),
            "planned_cost_usd": round(planned_usd, 6),
            "projected_total_usd": round(projected, 6),
            "hard_stop_total_usd": hard_stop, "network_calls_made": 0}


def agentsight_binary_identity(binary: str | Path, expected_sha256: str | None = None) -> dict:
    path = Path(binary).resolve(strict=True)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    sha256 = digest.hexdigest()
    if expected_sha256 and sha256.casefold() != expected_sha256.casefold():
        raise ValueError(f"AgentSight binary SHA-256 mismatch: expected {expected_sha256}, got {sha256}")
    return {"path": str(path), "sha256": sha256}


def diagnose_capture_coverage(counts: dict, network_targets: list[dict],
                              claude_pids: set[int]) -> dict:
    """Localize a missing layer without treating endpoint metadata as an LLM call."""
    llm_targets = [row for row in network_targets
                   if "/v1/messages" in (row.get("path") or "")]
    linked_pids = sorted({int(row["pid"]) for row in llm_targets
                          if row.get("pid") is not None and int(row["pid"]) in claude_pids})
    llm_calls = int(counts.get("llm_calls", 0))
    tool_calls = int(counts.get("tool_calls", 0))
    if not network_targets:
        stage = "process_to_network_capture"
        status = "no_network_targets"
    elif llm_calls == 0:
        stage = "network_to_llm_semantics"
        status = "endpoint_seen_but_llm_rows_missing"
    elif tool_calls == 0:
        stage = "llm_response_to_tool_semantics"
        status = "llm_rows_seen_but_tool_rows_missing"
    else:
        stage = "semantic_capture_present"
        status = "llm_and_tool_rows_present"
    return {
        "status": status,
        "first_unverified_stage": stage,
        "network_target_count": len(network_targets),
        "llm_endpoint_target_count": len(llm_targets),
        "endpoint_pid_matches_claude_process": bool(linked_pids),
        "matched_claude_pids": linked_pids,
        "llm_calls": llm_calls,
        "tool_calls": tool_calls,
        "interpretation": (
            "Host/path metadata is not proof that TLS bodies or semantic events were captured. "
            "This diagnosis localizes the missing layer but does not identify the exact parser/probe cause."
        ),
        "next_zero_cost_check": (
            "Compare a loopback HTTPS mock using the installed AgentSight binary with the same mock "
            "using a source-built binary; inspect HTTP request/response event body and TID before changing joins."
        ) if status == "endpoint_seen_but_llm_rows_missing" else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scenario", choices=tuple(SCENARIOS), required=True)
    parser.add_argument("--agents", nargs="+", choices=("agent_a", "agent_b"),
                        default=("agent_a", "agent_b"),
                        help="Agent sessions to run; agent_b requires agent_a's handoff")
    parser.add_argument("--agentsight-bin", default="agentsight",
                        help="AgentSight collector binary to use for record/debug/version")
    parser.add_argument("--expected-agentsight-sha256",
                        help="Refuse to start if the selected AgentSight binary differs from this SHA-256")
    parser.add_argument("--per-session-budget", type=float, default=0.12)
    parser.add_argument("--experiment-cost-cap-cny", type=float, default=2.0)
    parser.add_argument("--planning-usd-cny-rate", type=float, default=8.0,
                        help="Conservative planning conversion; not a live FX quote")
    repo_root = Path(__file__).resolve().parents[2]
    parser.add_argument("--cumulative-manifest", type=Path,
                        default=repo_root / "my_paper_coding" / "experiment_control" / "real-two-scenarios-plan-20261010.json")
    parser.add_argument("--cumulative-ledger", type=Path,
                        default=repo_root / "my_paper_coding" / "experiment_control" / "cost-ledger-20261012-sse-clock.json")
    parser.add_argument("--ignore-cumulative-budget", action="store_true",
                        help="Explicitly bypass only the historical cumulative hard stop; per-session and experiment caps remain enforced")
    parser.add_argument("--tool-id-bridge", action="store_true",
                        help="Install controlled PreToolUse/PostToolUse hook instrumentation for Bash tool IDs")
    args = parser.parse_args()
    if args.per_session_budget <= 0 or args.per_session_budget > 0.13:
        parser.error("Scenario gate allows at most 0.13 USD per CLI session")
    if args.experiment_cost_cap_cny <= 0 or args.experiment_cost_cap_cny > 2.0:
        parser.error("Per-experiment API cost cap must be positive and no more than 2 CNY")
    if args.planning_usd_cny_rate <= 0:
        parser.error("Planning USD/CNY rate must be positive")
    if len(set(args.agents)) != len(args.agents):
        parser.error("Each agent can be selected at most once")
    if "agent_b" in args.agents and "agent_a" not in args.agents:
        parser.error("agent_b requires agent_a to produce handoff.json")
    projection = budget_projection(args.per_session_budget, len(args.agents),
                                   args.planning_usd_cny_rate, args.experiment_cost_cap_cny)
    if not projection["within_cap"]:
        parser.error(f"Selected-session upper bound is {projection['projected_cny']:.4f} CNY, "
                     f"above the {args.experiment_cost_cap_cny:.2f} CNY experiment cap")
    try:
        cumulative_manifest = json.loads(args.cumulative_manifest.read_text(encoding="utf-8"))
        cumulative_ledger = json.loads(args.cumulative_ledger.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        parser.error(f"Cannot verify cumulative API budget; refusing to launch: {error}")
    cumulative_budget = cumulative_budget_preflight(
        cumulative_manifest, cumulative_ledger, projection["projected_usd"])
    if cumulative_budget["status"] != "PASS" and not args.ignore_cumulative_budget:
        parser.error("Cumulative API hard stop would be exceeded; refusing to launch: " +
                     json.dumps(cumulative_budget, ensure_ascii=False))
    try:
        agentsight_identity = agentsight_binary_identity(args.agentsight_bin,
                                                         args.expected_agentsight_sha256)
    except (OSError, ValueError) as error:
        parser.error(f"AgentSight binary identity check failed; refusing to launch: {error}")
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
    lifecycle_path = output / "observer-lifecycle.jsonl"
    lifecycle_path.touch(exist_ok=False)
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
    save(output / "plan.json", {"run_id": output.name, "scenario": args.scenario,
                                "agents": args.agents, "planned_cli_sessions": len(args.agents),
                                "per_session_budget_usd": args.per_session_budget,
                                "planned_batch_budget_usd": projection["projected_usd"],
                                "experiment_cost_cap_cny": args.experiment_cost_cap_cny,
                                "planning_usd_cny_rate": args.planning_usd_cny_rate,
                                "agentsight_binary": agentsight_identity,
                                "planned_batch_budget_cny": projection["projected_cny"],
                                "cumulative_budget_preflight": cumulative_budget,
                                "cumulative_budget_override": ({
                                    "enabled": True,
                                    "reason": "User explicitly authorized continuing real API tests regardless of the historical cumulative budget in this conversation",
                                    "historical_ledger_verification": "incomplete; this override does not claim historical spend was reconciled",
                                } if args.ignore_cumulative_budget else {"enabled": False}),
                                "tool_id_bridge": {
                                    "enabled": args.tool_id_bridge,
                                    "mode": "controlled_hook_instrumentation",
                                    "semantics": "PreToolUse supplies tool_use_id; only standalone allowlisted Python scenario scripts receive a tagged wrapper; PostToolUse closes the interval",
                                    "not_passive_agentsight": True,
                                },
                                "fx_note": "Planning conversion only; CLI-reported costs are not provider final billing",
                                "authorization": "User requested dataset expansion with API cost capped at 2 CNY per experiment; cumulative budget preflight remains separate",
                                "no_automatic_retry": True})
    save(output / "versions.json", {
        "claude": subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip(),
        "agentsight": subprocess.run([args.agentsight_bin, "--version"], capture_output=True, text=True).stdout.strip(),
        "agentsight_binary": agentsight_identity,
        "python3": subprocess.run(["python3", "--version"], capture_output=True, text=True).stdout.strip(),
    })
    db = output / "session.db"
    record_log, stream_log = (output / "record.log").open("x"), (output / "raw-stream.log").open("x")
    observer = subprocess.Popen([args.agentsight_bin, "record", "-c", "claude", "--db", str(db), "--no-server"],
                                stdout=record_log, stderr=subprocess.STDOUT, start_new_session=True)
    append_lifecycle(lifecycle_path, "record_spawned", observer)
    debug = None; summaries = []
    try:
        time.sleep(2)
        if observer.poll() is not None: raise RuntimeError("AgentSight exited before API invocation")
        append_lifecycle(lifecycle_path, "record_ready", observer)
        debug = subprocess.Popen([args.agentsight_bin, "debug", "process"], stdout=stream_log,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        append_lifecycle(lifecycle_path, "debug_spawned", observer, debug)
        time.sleep(1)
        if debug.poll() is not None: raise RuntimeError("Process observer exited before API invocation")
        append_lifecycle(lifecycle_path, "capture_ready", observer, debug)
        for agent_id in args.agents:
            if agent_id == "agent_b" and (not summaries or not summaries[-1]["success"]):
                break
            tools, prompt = spec[agent_id]
            append_lifecycle(lifecycle_path, f"{agent_id}_start", observer, debug)
            hook_events = (output / f"{agent_id}-tool-call-hook-events.jsonl"
                           if args.tool_id_bridge and "Bash" in tools.split(",") else None)
            summaries.append(capture_agent(output, agent_id, prompt.format(root=root), tools,
                                           args.per_session_budget, scope,
                                           tool_id_bridge_events=hook_events,
                                           allow_known_scenario_scripts=args.tool_id_bridge))
            append_lifecycle(lifecycle_path, f"{agent_id}_finished", observer, debug,
                             success=summaries[-1]["success"], stream_lines=summaries[-1]["stream_lines"])
            remaining_sessions = len(args.agents) - len(summaries)
            if (remaining_sessions and summaries[-1]["reported_cost_usd"] is not None
                    and not args.ignore_cumulative_budget):
                observed_cost = sum(float(item["reported_cost_usd"] or 0) for item in summaries)
                projected_total = (cumulative_budget["already_spent_usd"] + observed_cost
                                   + remaining_sessions * args.per_session_budget)
                if projected_total > cumulative_budget["hard_stop_total_usd"]:
                    append_lifecycle(lifecycle_path, "cumulative_hard_stop_before_next_session",
                                     observer, debug, projected_total_usd=round(projected_total, 6),
                                     hard_stop_total_usd=cumulative_budget["hard_stop_total_usd"])
                    break
        time.sleep(2)
    finally:
        append_lifecycle(lifecycle_path, "stop_requested", observer, debug)
        stop(observer)
        if debug is not None: stop(debug)
        append_lifecycle(lifecycle_path, "stopped", observer, debug)
        record_log.close(); stream_log.close()
        reported_cost_usd = sum(s["reported_cost_usd"] or 0 for s in summaries)
        cost_complete = bool(summaries) and all(s["reported_cost_usd"] is not None for s in summaries)
        reported_cost_cny = reported_cost_usd * args.planning_usd_cny_rate if cost_complete else None
        cost_cap_status = ("within_cap" if reported_cost_cny <= args.experiment_cost_cap_cny else "exceeded_cap") if cost_complete else "unknown"
        save(output / "capture-summary.json", {"agents": summaries,
             "reported_cost_usd": reported_cost_usd,
             "reported_cost_cny_at_planning_rate": reported_cost_cny,
             "cost_complete": cost_complete,
             "cost_cap_cny": args.experiment_cost_cap_cny,
             "cost_cap_status": cost_cap_status,
             "actual_cli_sessions": len(summaries), "scenario": args.scenario,
             "observer_lifecycle": lifecycle_path.name})
    counts = {}
    network_targets = []
    claude_pids: set[int] = set()
    if db.exists():
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as connection:
            for (table,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table'"):
                counts[table] = connection.execute('SELECT count(*) FROM "' + table.replace('"','""') + '"').fetchone()[0]
            if "network_targets" in counts:
                network_targets = [
                    {"pid": row[0], "comm": row[1], "host": row[2], "path": row[3], "count": row[4]}
                    for row in connection.execute(
                        "SELECT pid,comm,host,path,count FROM network_targets")
                ]
            if "process_nodes" in counts:
                claude_pids = {int(row[0]) for row in connection.execute(
                    "SELECT pid FROM process_nodes WHERE lower(comm) LIKE '%claude%' "
                    "OR lower(command) LIKE '%claude%'" )}
    save(output / "observation-counts.json", counts)
    save(output / "capture-coverage-diagnosis.json",
         diagnose_capture_coverage(counts, network_targets, claude_pids))
    print(json.dumps({"run_id": output.name, "scenario": args.scenario,
                      "agents": [{k: s[k] for k in ("agent_id", "success", "reported_cost_usd", "stream_lines")} for s in summaries],
                      "table_counts": counts}))
    return 0 if len(summaries) == len(args.agents) and all(s["success"] for s in summaries) and counts.get("tool_calls", 0) and cost_cap_status == "within_cap" else 2


if __name__ == "__main__":
    raise SystemExit(main())
