#!/usr/bin/env python3
"""Capture one real native framework session with process-tree and clock anchors."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import shutil
import socket
import sqlite3
import subprocess
import threading
import time
import uuid

from capture_real_application import save, stop


def clock_anchor():
    before = time.time_ns()
    mono = time.monotonic_ns()
    boot = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    after = time.time_ns()
    return {"realtime_interval_ns": [before, after], "realtime_midpoint_ns": (before + after) // 2,
            "realtime_uncertainty_ns": (after - before + 1) // 2,
            "monotonic_ns": mono, "boottime_ns": boot}


def proc_table():
    table = {}
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        try:
            stat = (path / "stat").read_text(encoding="utf-8")
            close = stat.rfind(")")
            pid = int(stat[:stat.find(" ")]); comm = stat[stat.find("(") + 1:close]
            fields = stat[close + 2:].split()
            table[pid] = {"pid": pid, "ppid": int(fields[1]), "comm": comm,
                          "start_ticks": int(fields[19])}
        except (OSError, ValueError, IndexError):
            continue
    return table


def descendants(root: int):
    table = proc_table(); selected = {root}; changed = True
    while changed:
        changed = False
        for pid, value in table.items():
            if value["ppid"] in selected and pid not in selected:
                selected.add(pid); changed = True
    result = []
    for pid in sorted(selected):
        if pid not in table:
            continue
        value = table[pid]
        try:
            status = (Path(f"/proc/{pid}/status").read_text(encoding="utf-8", errors="replace"))
            nspid = next(([int(part) for part in line.split(":", 1)[1].split()]
                          for line in status.splitlines() if line.startswith("NSpid:")), [])
            value.update(nspid=nspid, pid_namespace_link=os.readlink(f"/proc/{pid}/ns/pid"))
        except OSError:
            value.update(nspid=[], pid_namespace_link=None)
        result.append(value)
    return result


def sample_processes(root: int, path: Path, stopped: threading.Event):
    with path.open("x", encoding="utf-8") as stream:
        while not stopped.is_set():
            stream.write(json.dumps({"clock": clock_anchor(), "root_pid": root,
                                     "processes": descendants(root)}) + "\n")
            stream.flush()
            stopped.wait(0.05)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--per-session-budget", type=float, default=0.10)
    parser.add_argument("--agentsight-binary", default="agentsight")
    args = parser.parse_args()
    if not 0 < args.per_session_budget <= 0.10:
        parser.error("Budget must be within (0, 0.10]")
    if os.geteuid() != 0:
        parser.error("Run as root in the configured Ubuntu WSL distribution")
    if not (os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")):
        parser.error("Missing existing API credential")
    from urllib.parse import urlparse
    host = urlparse(os.environ.get("ANTHROPIC_BASE_URL", "https://api.deepseek.com")).hostname
    socket.getaddrinfo(host, 443)
    experiment = args.experiment.resolve()
    agentsight_binary = shutil.which(args.agentsight_binary) or args.agentsight_binary
    agentsight_path = Path(agentsight_binary).resolve()
    if not agentsight_path.is_file():
        parser.error(f"AgentSight binary does not exist: {agentsight_path}")
    agentsight_sha256 = hashlib.sha256(agentsight_path.read_bytes()).hexdigest()
    results = experiment / "results"; results.mkdir(parents=True, exist_ok=False)
    workspace = results / "workspace"; workspace.mkdir()
    os.environ["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    if not Path("/sys/kernel/tracing/events/sched/sched_process_exec").exists():
        subprocess.run(["mount", "-t", "tracefs", "tracefs", "/sys/kernel/tracing"], check=True)
    session = str(uuid.uuid4())
    host_id = hashlib.sha256(Path("/etc/machine-id").read_bytes()).hexdigest()
    scope = {"host_id": host_id, "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
             "pid_namespace": os.readlink("/proc/self/ns/pid"), "clock_ticks_per_second": os.sysconf("SC_CLK_TCK"),
             "observer_pid_namespace": "linux-initial-pid-namespace",
             "capture_start": clock_anchor(), "framework": "Claude Code CLI stream-json"}
    save(results / "capture-scope.json", scope)
    versions = {name: subprocess.run([name, "--version"], capture_output=True, text=True).stdout.strip()
                for name in ("claude", "python3")}
    versions["agentsight"] = subprocess.run([str(agentsight_path), "--version"], capture_output=True,
                                              text=True).stdout.strip()
    versions["agentsight_binary"] = str(agentsight_path)
    versions["agentsight_sha256"] = agentsight_sha256
    save(results / "versions.json", versions)
    db = results / "session.db"
    record_log = (results / "agentsight-record.log").open("x")
    debug_log = (results / "agentsight-debug.log").open("x")
    observer = subprocess.Popen([str(agentsight_path), "record", "-c", "claude", "--db", str(db), "--no-server"],
                                stdout=record_log, stderr=subprocess.STDOUT, start_new_session=True)
    debug = None; process = None; sampler = None; stopped = threading.Event()
    stderr = raw = receipts = None; result_rows = []; native_types = []; line_number = 0
    try:
        time.sleep(2)
        if observer.poll() is not None:
            raise RuntimeError("AgentSight recorder exited before API invocation")
        debug = subprocess.Popen([str(agentsight_path), "debug", "process"], stdout=debug_log,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        time.sleep(1)
        probe = Path(__file__).resolve().parent / "process_clock_probe.py"
        prompt = (f'Use Bash exactly once to run python3 "{probe}". '
                  'Return a brief confirmation after the tool succeeds. Do not use any other tool.')
        command = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
                   "--include-partial-messages", "--include-hook-events", "--session-id", session,
                   "--model", os.environ.get("ANTHROPIC_MODEL", "deepseek-v4-pro"),
                   "--tools", "Bash", "--allowedTools", "Bash", "--max-budget-usd", str(args.per_session_budget),
                   "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"]
        stderr = (results / "claude-stderr.log").open("x")
        launch_before = clock_anchor()
        process = subprocess.Popen(command, cwd=workspace, stdout=subprocess.PIPE, stderr=stderr, start_new_session=True)
        launch_after = clock_anchor()
        save(results / "launch.json", {"session_id": session, "launcher_pid": process.pid,
             "launch_before": launch_before, "launch_after": launch_after,
             "launch_wall_uncertainty_ms": math.ceil((launch_after["realtime_midpoint_ns"] - launch_before["realtime_midpoint_ns"]) / 2e6) + 2,
             "pid_namespace": os.readlink(f"/proc/{process.pid}/ns/pid")})
        sampler = threading.Thread(target=sample_processes,
                                   args=(process.pid, results / "process-samples.jsonl", stopped), daemon=True)
        sampler.start()
        raw = (results / "framework-native.jsonl").open("xb")
        receipts = (results / "framework-receipts.jsonl").open("x", encoding="utf-8")
        selector = selectors.DefaultSelector(); selector.register(process.stdout, selectors.EVENT_READ)
        buffer = b""; deadline = time.monotonic() + 150; timed_out = False

        def consume(line: bytes):
            nonlocal line_number
            line_number += 1; raw.write(line + b"\n"); raw.flush()
            anchor = clock_anchor(); receipts.write(json.dumps({"line": line_number, **anchor}) + "\n"); receipts.flush()
            try: value = json.loads(line)
            except (ValueError, UnicodeError): return
            if isinstance(value, dict):
                native_types.append({"line": line_number, "type": value.get("type"), "subtype": value.get("subtype")})
                if value.get("type") == "result": result_rows.append(value)

        while selector.get_map():
            if time.monotonic() > deadline:
                timed_out = True; stop(process); break
            for key, _ in selector.select(timeout=0.2):
                data = os.read(key.fileobj.fileno(), 65536)
                if not data:
                    selector.unregister(key.fileobj); continue
                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1); consume(line)
        if buffer: consume(buffer)
        process.wait(timeout=5); selector.close()
        terminal = result_rows[-1] if result_rows else {}
        save(results / "capture-summary.json", {"session_id": session, "launcher_pid": process.pid,
             "exit_code": process.returncode, "timed_out": timed_out, "native_lines": line_number,
             "native_types": native_types, "reported_cost_usd": terminal.get("total_cost_usd"),
             "usage": terminal.get("usage"), "model_usage": terminal.get("modelUsage"),
             "success": process.returncode == 0 and bool(terminal) and not terminal.get("is_error", True)})
        time.sleep(2)
    finally:
        stopped.set()
        if sampler is not None: sampler.join(timeout=3)
        if process is not None: stop(process)
        stop(observer)
        if debug is not None: stop(debug)
        for stream in (stderr, raw, receipts, record_log, debug_log):
            if stream is not None: stream.close()
    counts = {}
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as connection:
        for (table,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            counts[table] = connection.execute('SELECT count(*) FROM "' + table.replace('"', '""') + '"').fetchone()[0]
    save(results / "observation-counts.json", counts)
    success = json.loads((results / "capture-summary.json").read_text())["success"]
    print(json.dumps({"experiment": experiment.name, "success": success, "cost_usd":
                      json.loads((results / "capture-summary.json").read_text())["reported_cost_usd"],
                      "table_counts": counts}))
    return 0 if success and counts.get("tool_calls", 0) else 2


if __name__ == "__main__":
    raise SystemExit(main())
