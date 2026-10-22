#!/usr/bin/env python3
"""No-credential DeepSeek rejection probe for AgentSight capture diagnostics.

This sends only a synthetic prompt with a deliberately invalid key. A 2xx
response is treated as a safety failure; the script does not use real secrets.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from probe_agentsight_local_mock import db_summary, stop


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("requires root for AgentSight eBPF")
    output = args.output.resolve()
    if output.exists():
        parser.error(f"refusing to overwrite: {output}")
    output.mkdir(parents=True)
    home = output / "isolated-home"
    home.mkdir()
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(home), "LANG": "C.UTF-8",
        "ANTHROPIC_AUTH_TOKEN": "agentsight-invalid-rejection-probe-key",
        "ANTHROPIC_API_KEY": "agentsight-invalid-rejection-probe-key",
        "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
        "ANTHROPIC_MODEL": "deepseek-chat",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "DISABLE_TELEMETRY": "1",
    }
    db = output / "session.db"
    with (output / "record.log").open("wb") as record_log:
        recorder = subprocess.Popen(
            ["agentsight", "record", "-c", "claude", "--db", str(db), "--no-server"],
            cwd=output, env=env, stdout=record_log, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            time.sleep(4)
            if recorder.poll() is not None:
                raise RuntimeError("AgentSight exited before the CLI started")
            command = [
                "claude", "-p", "agentsight-invalid-key-rejection-probe-20261020",
                "--model", "deepseek-chat", "--output-format", "json",
                "--tools", "", "--allowedTools", "", "--max-turns", "1",
                "--setting-sources", "", "--strict-mcp-config",
                "--disable-slash-commands", "--no-session-persistence",
            ]
            with (output / "claude.log").open("wb") as cli_log:
                cli = subprocess.Popen(command, cwd=output, env=env, stdout=cli_log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    cli_exit = cli.wait(timeout=45)
                    cli_timed_out = False
                except subprocess.TimeoutExpired:
                    cli_timed_out = True
                    stop(cli)
                    cli_exit = 124
            time.sleep(2)
        finally:
            stop(recorder)
    cli_text = (output / "claude.log").read_text(encoding="utf-8", errors="replace")
    lower = cli_text.lower()
    rejected = any(marker in lower for marker in ("401", "unauthorized", "invalid api key", "authentication"))
    result = {
        "experiment_kind": "invalid-key-rejected-endpoint-probe",
        "real_credentials_loaded": False,
        "paid_inference_authorized": False,
        "synthetic_prompt_only": True,
        "provider": "api.deepseek.com/anthropic",
        "cli_exit_code": cli_exit,
        "cli_timed_out": cli_timed_out,
        "rejection_marker_present": rejected,
        "recorder_exit_code": recorder.returncode,
        "database": db_summary(db),
        "interpretation_rule": "Only a clearly rejected request can be considered no-cost; if rejection is not confirmed, do not infer cost or success.",
    }
    (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return 0 if rejected and not cli_timed_out else 2


if __name__ == "__main__":
    raise SystemExit(main())
