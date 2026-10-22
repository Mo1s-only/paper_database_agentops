#!/usr/bin/env python3
"""Controlled Claude PreToolUse hook that tags a single-command Bash exec argv.

This is an experimental ground-truth bridge, not passive AgentSight behavior.
Only a validated opaque tool ID is added; the original command is never logged.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile
import time


TOOL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


KNOWN_SCENARIO_SCRIPTS = {
    "scenario_service_observer.py",
    "scenario_service_decider.py",
    "scenario_faulty_router.py",
    "scenario_route_executor.py",
    "public_dataset_runtime_probe.py",
}


@contextmanager
def locked_jsonl_append(path: Path):
    """Append one complete JSONL record while serializing independent hook processes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_key = hashlib.sha256(str(path.resolve()).encode("utf-8", errors="replace")).hexdigest()
    lock_path = Path(tempfile.gettempdir()) / "agentops-hook-locks" / f"{lock_key}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_stream:
        if lock_stream.seek(0, 2) == 0:
            lock_stream.write(b"\0")
            lock_stream.flush()
        lock_stream.seek(0)
        if os.name == "nt":
            import msvcrt
            deadline = time.monotonic() + 30
            while True:
                try:
                    msvcrt.locking(lock_stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Timed out waiting for the hook JSONL append lock")
                    time.sleep(0.02)
        else:
            import fcntl
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
        try:
            with path.open("a", encoding="utf-8", newline="") as stream:
                yield stream
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            if os.name == "nt":
                msvcrt.locking(lock_stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)


def is_known_scenario_command(command: str) -> bool:
    """Only permit argv tagging for a standalone, allowlisted Python scenario command."""
    try:
        argv = shlex.split(command, posix=True)
    except ValueError:
        return False
    shell_operators = {";", "&&", "||", "|", "&", ">", ">>", "<", "<<"}
    return (
        len(argv) >= 2
        and Path(argv[0]).name == "python3"
        and Path(argv[1]).name in KNOWN_SCENARIO_SCRIPTS
        and not any(token in shell_operators for token in argv)
    )


def process_hook(payload: dict, event_path: Path,
                 allow_known_scenario_scripts: bool = False) -> dict | None:
    hook_name = payload.get("hook_event_name")
    if hook_name not in {"PreToolUse", "PostToolUse"} or payload.get("tool_name") != "Bash":
        return None
    tool_id = payload.get("tool_use_id")
    if not isinstance(tool_id, str) or not TOOL_ID_RE.fullmatch(tool_id):
        return None
    if hook_name == "PostToolUse":
        with locked_jsonl_append(event_path) as stream:
            stream.write(json.dumps({
                "hook_event_name": hook_name,
                "tool_name": "Bash",
                "tool_call_id": tool_id,
                "received_wall_time_ns": time.time_ns(),
            }) + "\n")
            stream.flush()
        return None

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict) or not isinstance(tool_input.get("command"), str):
        return None

    command = tool_input["command"]
    marker = f"AGENTOPS_TOOL_CALL_ID={tool_id}"
    # The controlled next-stage canary contains a compound Bash command. Start
    # that command in a tagged Bash wrapper: sched_process_exec captures the ID
    # on the wrapper PID, and PPID links all command processes back to it.
    # This is scoped to the known canary command, not arbitrary user input
    # where introducing a nested shell could change semantics.
    command_tagged = (
        command.lstrip().startswith("python3 ")
        and "scenario_service_observer.py" in command
        and "&& /bin/true" in command
    )
    if allow_known_scenario_scripts and is_known_scenario_command(command):
        command_tagged = True
    updated_command = (
        f"exec -a '{marker}' bash -c {shlex.quote(command)}"
        if command_tagged else command
    )
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_call_id": tool_id,
        "command_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
        "command_tagged": command_tagged,
        "received_wall_time_ns": time.time_ns(),
    }
    with locked_jsonl_append(event_path) as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        stream.flush()

    updated_input = dict(tool_input)
    updated_input["command"] = updated_command
    if not command_tagged:
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": updated_input,
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--allow-known-scenario-scripts", action="store_true")
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    if not isinstance(payload, dict):
        return 0
    # Pass the experiment-only wrapping policy without adding it to hook input.
    result = process_hook(payload, args.events,
                          allow_known_scenario_scripts=args.allow_known_scenario_scripts)
    if result is not None:
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
