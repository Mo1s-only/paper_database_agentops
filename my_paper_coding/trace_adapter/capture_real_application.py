#!/usr/bin/env python3
"""Real Claude/AgentSight canary on Linux; two bounded sessions, no automatic retries."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import signal
import socket
import sqlite3
import subprocess
import time
import uuid


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def wall_ms():
    return time.time_ns() / 1000000


def stop(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGINT)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def process_views(pid):
    """Snapshot Linux namespace PID views while the process is alive."""
    status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8", errors="replace")
    values = {}
    for line in status.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            if key in {"Pid", "PPid", "NSpid"}:
                values[key.lower()] = [int(x) for x in value.split()]
    values["pid_namespace_link"] = os.readlink(f"/proc/{pid}/ns/pid")
    values["captured_at_ms"] = round(wall_ms())
    return values


def capture_agent(output, agent, prompt, tools, budget, scope):
    session = str(uuid.uuid4())
    command = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
               "--include-partial-messages", "--include-hook-events", "--session-id", session,
               "--model", os.environ.get("ANTHROPIC_MODEL", "deepseek-v4-pro"),
               "--tools", tools, "--allowedTools", tools, "--max-budget-usd", str(budget),
               "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
               "--no-session-persistence"]
    stderr = (output / f"{agent}-stderr.log").open("x")
    before_wall, before_mono = wall_ms(), time.monotonic_ns()
    process = subprocess.Popen(command, cwd=output / "workspace", stdout=subprocess.PIPE, stderr=stderr,
                               start_new_session=True)
    after_wall, after_mono = wall_ms(), time.monotonic_ns()
    views = process_views(process.pid)
    uncertainty = math.ceil((after_wall - before_wall) / 2) + 2
    metadata = {"agent_id": agent, "session_id": session, "pid": process.pid,
                "process": {"host_id": scope["host_id"], "boot_id": scope["boot_id"],
                            "pid_namespace": scope["pid_namespace"], "pid": process.pid,
                            "start_ms": round((before_wall + after_wall) / 2)},
                "clock": {"domain": scope["clock_domain"], "uncertainty_ms": uncertainty},
                "launch_interval_ms": [before_wall, after_wall],
                "launch_monotonic_ns": [before_mono, after_mono],
                "process_start_semantics": "bounded exec time estimate from Popen before/after; not kernel birth time",
                "start_bound_includes_fork_exec": True,
                "pid_views": views,
                "budget_usd": budget, "command": command}
    save(output / f"{agent}-launch.json", metadata)
    results, messages, raw_lines = [], [], 0
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    buffer = b""
    deadline = time.monotonic() + 150
    raw = (output / f"claude-agent-{agent[-1]}.log").open("xb")
    timing = (output / f"{agent}-receipt-times.jsonl").open("x")
    timed_out = False

    def consume(line):
        nonlocal raw_lines
        raw_lines += 1
        raw.write(line + b"\n"); raw.flush()
        received = {"line": raw_lines, "received_at_ms": round(wall_ms()), "received_monotonic_ns": time.monotonic_ns()}
        timing.write(json.dumps(received) + "\n"); timing.flush()
        try:
            value = json.loads(line)
        except (ValueError, UnicodeError):
            return
        if isinstance(value, dict):
            messages.append({"line": raw_lines, "type": value.get("type"), "subtype": value.get("subtype")})
            if value.get("type") == "result":
                results.append(value)

    try:
        while selector.get_map():
            if time.monotonic() > deadline:
                timed_out = True
                stop(process)
                break
            for key, _ in selector.select(timeout=0.2):
                data = os.read(key.fileobj.fileno(), 65536)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    consume(line)
        if buffer:
            consume(buffer)
        process.wait(timeout=5)
    finally:
        stop(process)
        raw.close(); timing.close(); stderr.close(); selector.close()
    result = results[-1] if results else {}
    summary = {"agent_id": agent, "session_id": session, "pid": process.pid,
               "exit_code": process.returncode, "timed_out": timed_out, "stream_lines": raw_lines,
               "message_types": messages, "reported_cost_usd": result.get("total_cost_usd"),
               "usage": result.get("usage"), "modelUsage": result.get("modelUsage"),
               "result_subtype": result.get("subtype"), "is_error": result.get("is_error"),
               "success": process.returncode == 0 and bool(result) and not result.get("is_error", True)}
    save(output / f"{agent}-capture-summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-session-budget", type=float, default=0.20)
    parser.add_argument("--scenario", choices=("original", "complete-v1"), default="original")
    args = parser.parse_args()
    if args.per_session_budget <= 0 or args.per_session_budget > 0.20:
        parser.error("This canary allows a positive per-session budget of at most 0.20 USD")
    if os.geteuid() != 0:
        parser.error("Run in the known Ubuntu WSL distribution as root for eBPF")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "workspace").mkdir()
    os.environ["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    # Never print or persist credentials/environment values.
    if not (os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")):
        parser.error("Missing existing credential")
    from urllib.parse import urlparse
    endpoint = urlparse(os.environ.get("ANTHROPIC_BASE_URL", "https://api.deepseek.com"))
    socket.getaddrinfo(endpoint.hostname, 443)
    if not Path("/sys/kernel/tracing/events/sched/sched_process_exec").exists():
        subprocess.run(["mount", "-t", "tracefs", "tracefs", "/sys/kernel/tracing"], check=True)
    if not Path("/sys/kernel/tracing/events/sched/sched_process_exec").exists():
        parser.error("Missing exec tracepoint")
    scope = {"schema_version": "agentops-observation-scope-v0.1", "run_id": output.name,
             "evidence_kind": "runtime_observed", "host_id": hashlib.sha256(Path("/etc/machine-id").read_bytes()).hexdigest(),
             "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
             "pid_namespace": os.readlink("/proc/self/ns/pid"), "clock_domain": "linux-CLOCK_REALTIME-ms",
             "uncertainty_ms": 1,
             "clock_boundary": "Same Linux kernel wall clock; 1ms quantization bound, no network-clock claim"}
    save(output / "capture-scope.json", scope)
    save(output / "plan.json", {"run_id": output.name, "planned_cli_sessions": 2,
                                "per_session_budget_usd": args.per_session_budget,
                                "planned_batch_budget_usd": 2 * args.per_session_budget,
                                "authorization": "User explicitly requested real API calls in this chat",
                                "no_automatic_retry": True, "scenario": args.scenario})
    if args.scenario == "complete-v1":
        save(output / "ground_truth.json", {
            "schema_version": "agentops-ground-truth-v0.2", "created_before_api": True,
            "fault_type": "silent_tool_error", "responsible_agent": "agent_b",
            "responsible_step": "agent_b.inventory_bash_call",
            "task_requirement": {"item": "alpha", "available": 1},
            "faulty_tool_behavior": {"item": "alpha", "available": 0},
            "truth_source": "fixed local tool implementation and task requirement; excluded from agent workspace and alignment inputs"
        })
    versions = {name: subprocess.run([name, "--version"], capture_output=True, text=True).stdout.strip()
                for name in ("claude", "agentsight", "python3")}
    save(output / "versions.json", versions)
    db = output / "session.db"
    record_log, stream_log = (output / "record.log").open("x"), (output / "raw-stream.log").open("x")
    observer = subprocess.Popen(["agentsight", "record", "-c", "claude", "--db", str(db), "--no-server"],
                                stdout=record_log, stderr=subprocess.STDOUT, start_new_session=True)
    debug = None
    summaries = []
    try:
        time.sleep(2)
        if observer.poll() is not None:
            raise RuntimeError("AgentSight exited before API invocation")
        debug = subprocess.Popen(["agentsight", "debug", "process"], stdout=stream_log,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        time.sleep(1)
        if debug.poll() is not None:
            raise RuntimeError("Process observer exited before API invocation")
        prompt_a = 'You are Agent A, a planner. Use Write exactly once to create route.json containing {"item":"alpha","required_available":1}. Then finish briefly. Do not use any other tool.'
        if args.scenario == "complete-v1":
            executor = Path(__file__).resolve().parent / "complete_inventory_tool.py"
            prompt_b = f'You are Agent B, an executor. Use Bash exactly once to run python3 "{executor}" route.json. Treat its JSON output as the actual route and inventory observation. Then use Write exactly once to create decision.json with item, required_available, observed_available, satisfied. Derive satisfied from the actual values. Finish briefly. Use only Bash and Write; do not inspect any other files.'
            tools_b = "Bash,Write"
        else:
            tool = Path(__file__).resolve().parent.parent / "failure_pilot" / "fake_inventory.py"
            prompt_b = f'You are Agent B, an executor. Use Read to read route.json, then Bash to run python3 "{tool}" alpha. From the actual tool result and route requirement, use Write to create decision.json with item, required_available, observed_available, satisfied. Finish briefly. Use only Read, Bash, Write; do not inspect any other files.'
            tools_b = "Read,Bash,Write"
        summaries.append(capture_agent(output, "agent_a", prompt_a, "Write", args.per_session_budget, scope))
        if summaries[-1]["success"] and observer.poll() is None:
            summaries.append(capture_agent(output, "agent_b", prompt_b, tools_b, args.per_session_budget, scope))
        time.sleep(2)
    finally:
        stop(observer)
        if debug is not None:
            stop(debug)
        record_log.close(); stream_log.close()
        save(output / "capture-summary.json", {"agents": summaries,
             "reported_cost_usd": sum(s["reported_cost_usd"] or 0 for s in summaries),
             "cost_complete": bool(summaries) and all(s["reported_cost_usd"] is not None for s in summaries),
             "actual_cli_sessions": len(summaries)})
    counts = {}
    if db.exists():
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
                counts[table] = conn.execute('SELECT count(*) FROM "' + table.replace('"','""') + '"').fetchone()[0]
    save(output / "observation-counts.json", counts)
    print(json.dumps({"run_id": output.name, "agents": [{k: s[k] for k in ("agent_id","success","reported_cost_usd","stream_lines")} for s in summaries], "table_counts": counts}))
    return 0 if len(summaries) == 2 and all(s["success"] for s in summaries) and counts.get("tool_calls", 0) > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
