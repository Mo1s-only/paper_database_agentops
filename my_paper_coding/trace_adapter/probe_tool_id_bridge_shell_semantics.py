#!/usr/bin/env python3
"""Zero-API Bash semantics probe for the experimental argv-tagging wrapper."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import time


MARKER = "AGENTOPS_TOOL_CALL_ID=call_semantics_probe"


def run_shell(script: str, env: dict[str, str]) -> dict:
    result = subprocess.run(["/bin/bash", "-c", script], capture_output=True,
                            text=True, env=env, check=False)
    return {"returncode": result.returncode, "stdout": result.stdout,
            "stderr": result.stderr}


def compare_case(name: str, command: str, prelude: str = "", env: dict[str, str] | None = None) -> dict:
    environment = dict(env or {})
    baseline = run_shell(prelude + "\n" + command, environment)
    wrapped = run_shell(prelude + "\nexec -a " + shlex.quote(MARKER)
                        + " /bin/bash -c " + shlex.quote(command), environment)
    return {"name": name, "baseline": baseline, "tagged_wrapper": wrapped,
            "behavior_equal": baseline == wrapped}


def probe() -> dict:
    common_env = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                  "AGENTOPS_PROBE_EXPORT": "visible"}
    cases = [
        compare_case("exported_environment", "printf 'env=%s\\n' \"$AGENTOPS_PROBE_EXPORT\"",
                     env=common_env),
        compare_case("cd_and_command_in_same_tool", "cd /tmp && pwd", env=common_env),
        compare_case("snapshot_function", "snapshot_fn", "snapshot_fn() { printf 'function=available\\n'; }",
                     common_env),
        compare_case("inherited_pipefail", "false | true; printf 'pipeline_status=%s\\n' \"$?\"",
                     "set -o pipefail", common_env),
        compare_case("inherited_errexit", "false; printf 'reached\\n'", "set -e", common_env),
    ]
    return {
        "schema_version": "tool-id-bridge-shell-semantics-probe-v0.1",
        "created_wall_time_ns": time.time_ns(),
        "api_calls": 0,
        "cases": cases,
        "summary": {
            "equal_cases": sum(case["behavior_equal"] for case in cases),
            "total_cases": len(cases),
            "known_divergences": [case["name"] for case in cases if not case["behavior_equal"]],
        },
        "interpretation_limit": (
            "This compares a shell with preloaded local state against the exact nested-Bash argv wrapper. "
            "It does not emulate Claude Code's complete shell snapshot or prove every command changes behavior."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = probe()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
