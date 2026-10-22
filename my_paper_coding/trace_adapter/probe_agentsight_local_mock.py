#!/usr/bin/env python3
"""Zero-cost, loopback-only probe of Claude Code -> AgentSight TLS capture.

No real provider URL or credential is read. Both tested CLI invocations use an
isolated HOME, a fake API key, a local HTTPS mock, and a dead external proxy.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import socket
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request


REPO = Path(__file__).resolve().parents[2]
MOCK_SERVER = REPO / "lab/agentsight/source/thesis_adapter/script/e2e/mock_llm_server.py"
SSE_SERVER = Path(__file__).with_name("mock_anthropic_sse.py")
H2_SERVER = Path(__file__).with_name("mock_anthropic_h2.js")
PROMPT = "agentsight-local-only-canary-20261019: reply with the mock response"


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def choose_port() -> int:
    with socket.socket() as address:
        address.bind(("127.0.0.1", 0))
        return address.getsockname()[1]


def stop(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGINT)
    try:
        process.wait(timeout=12)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def cli_environment(home: Path, port: int, base_path: str = "", model: str = "claude-agentsight-mock") -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=False)
    # Whitelist instead of copying os.environ: no existing API key, proxy
    # credential, Claude login, or provider endpoint can enter this process.
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "ANTHROPIC_API_KEY": "agentsight-local-test-not-a-real-key",
        "ANTHROPIC_AUTH_TOKEN": "agentsight-local-test-not-a-real-key",
        "ANTHROPIC_BASE_URL": f"https://127.0.0.1:{port}{base_path}",
        "ANTHROPIC_MODEL": model,
        "NODE_TLS_REJECT_UNAUTHORIZED": "0",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "DISABLE_TELEMETRY": "1",
        "HTTP_PROXY": "http://127.0.0.1:9",
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "NO_PROXY": "127.0.0.1,localhost",
    }


def cli_command(tools_enabled: bool, model: str) -> list[str]:
    command = ["claude", "-p", PROMPT, "--output-format", "json",
               "--model", model,
               "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
               "--no-session-persistence"]
    if not tools_enabled:
        command.extend(["--tools", "", "--allowedTools", ""])
    return command


def launch_cli(work: Path, env: dict[str, str], tools_enabled: bool, model: str) -> tuple[int, bool]:
    command = cli_command(tools_enabled, model)
    with (work / "claude-stdout.json").open("wb") as stdout, (work / "claude-stderr.log").open("wb") as stderr:
        process = subprocess.Popen(command, cwd=work, env=env, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        timed_out = False
        try:
            code = process.wait(timeout=75)
        except subprocess.TimeoutExpired:
            timed_out = True
            stop(process)
            code = 124
    return code, timed_out


def db_summary(db: Path) -> dict:
    if not db.is_file():
        return {"exists": False}
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts = {table: connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
                  for table in ("llm_calls", "tool_calls", "token_usage", "network_targets", "process_nodes", "audit_events")
                  if table in tables}
        audits = (connection.execute("SELECT audit_type,count(*) FROM audit_events GROUP BY audit_type").fetchall()
                  if "audit_events" in tables else [])
        hosts = (connection.execute("SELECT DISTINCT host FROM network_targets ORDER BY host").fetchall()
                 if "network_targets" in tables else [])
    return {"exists": True, "counts": counts, "audit_types": dict(audits),
            "network_hosts": [row[0] for row in hosts]}


def mock_entries(log: Path) -> list[dict]:
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line]


def run_wrapped(output: Path, env: dict[str, str], mock_log: Path, tools_enabled: bool, model: str) -> dict:
    work = output / "wrapped"
    work.mkdir()
    env = {**env, "HOME": str(work / "home")}
    Path(env["HOME"]).mkdir()
    db = work / "session.db"
    before = len(mock_entries(mock_log))
    command = ["agentsight", "record", "--no-server", "--db", str(db), "--"] + cli_command(tools_enabled, model)
    with (work / "record-stdout.log").open("wb") as stdout, (work / "record-stderr.log").open("wb") as stderr:
        process = subprocess.Popen(command, cwd=work, env=env, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        timed_out = False
        try:
            code = process.wait(timeout=95)
        except subprocess.TimeoutExpired:
            timed_out = True
            stop(process)
            code = 124
    entries = mock_entries(mock_log)[before:]
    return {"mode": "wrapped", "recorder_exit_code": code, "timed_out": timed_out,
            "mock_request_count": len(entries), "mock_paths": [x.get("path") for x in entries],
            "prompt_reached_mock": any(PROMPT in x.get("prompt", "") for x in entries),
            "database": db_summary(db)}


def run_detached(output: Path, env: dict[str, str], mock_log: Path, tools_enabled: bool, model: str) -> dict:
    work = output / "detached"
    work.mkdir()
    env = {**env, "HOME": str(work / "home")}
    Path(env["HOME"]).mkdir()
    db = work / "session.db"
    before = len(mock_entries(mock_log))
    with (work / "record-stdout.log").open("wb") as stdout, (work / "record-stderr.log").open("wb") as stderr:
        recorder = subprocess.Popen(["agentsight", "record", "-c", "claude", "--db", str(db),
                                     "--no-server"], cwd=work, env=env, stdout=stdout, stderr=stderr,
                                    start_new_session=True)
        try:
            time.sleep(4)
            ready_before_cli = recorder.poll() is None
            if ready_before_cli:
                cli_code, cli_timed_out = launch_cli(work, env, tools_enabled, model)
                time.sleep(2)
            else:
                cli_code, cli_timed_out = None, False
        finally:
            stop(recorder)
    entries = mock_entries(mock_log)[before:]
    return {"mode": "detached", "recorder_ready_before_cli": ready_before_cli,
            "recorder_exit_code": recorder.returncode, "cli_exit_code": cli_code,
            "cli_timed_out": cli_timed_out, "mock_request_count": len(entries),
            "mock_paths": [x.get("path") for x in entries],
            "prompt_reached_mock": any(PROMPT in x.get("prompt", "") for x in entries),
            "database": db_summary(db)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-path", choices=("", "/anthropic"), default="",
                        help="Optional DeepSeek-compatible URL prefix for a local-only path test")
    parser.add_argument("--mode", choices=("both", "wrapped", "detached"), default="both")
    parser.add_argument("--sse", action="store_true", help="Use local Anthropic event-stream responses")
    parser.add_argument("--h2", action="store_true", help="Offer HTTP/2 ALPN on the local mock")
    parser.add_argument("--tools-enabled", action="store_true", help="Include default Claude tool schemas")
    parser.add_argument("--model", default="claude-agentsight-mock")
    args = parser.parse_args()
    if not MOCK_SERVER.is_file() or os.geteuid() != 0:
        parser.error("requires the local mock server and Ubuntu root for eBPF")
    output = args.output.resolve()
    if output.exists():
        parser.error(f"refusing to overwrite: {output}")
    output.mkdir(parents=True)
    port = choose_port()
    mock_log = output / "mock-requests.jsonl"
    with tempfile.TemporaryDirectory(prefix="agentsight-local-mock-") as temporary:
        temp = Path(temporary)
        cert, key = temp / "mock.crt", temp / "mock.key"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                        "-keyout", str(key), "-out", str(cert), "-days", "1",
                        "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        with (output / "mock-server-stdout.log").open("wb") as stdout, (output / "mock-server-stderr.log").open("wb") as stderr:
            if args.h2:
                server_command = ["node", str(H2_SERVER), "--port", str(port), "--log", str(mock_log),
                                  "--tls-cert", str(cert), "--tls-key", str(key)]
            else:
                server_command = [sys.executable, str(SSE_SERVER if args.sse else MOCK_SERVER),
                                  "--host", "127.0.0.1", "--port", str(port), "--log", str(mock_log),
                                  "--tls-cert", str(cert), "--tls-key", str(key), "--quiet"]
            server = subprocess.Popen(server_command,
                                      stdout=stdout, stderr=stderr, start_new_session=True)
            try:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                                     urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
                for _ in range(50):
                    try:
                        with opener.open(f"https://127.0.0.1:{port}/health", timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise RuntimeError("local mock HTTPS server did not become healthy")
                env = cli_environment(output / "isolated-home", port, args.base_path, args.model)
                wrapped = run_wrapped(output, env, mock_log, args.tools_enabled, args.model) if args.mode in ("both", "wrapped") else None
                detached = run_detached(output, env, mock_log, args.tools_enabled, args.model) if args.mode in ("both", "detached") else None
            finally:
                stop(server)
    result = {"experiment_kind": "zero_cost_local_https_mock", "paid_provider_requests_authorized": False,
              "real_credentials_loaded": False, "provider_base_url": "127.0.0.1 loopback only",
              "fake_credential_only": True, "external_proxy": "127.0.0.1:9 (dead)",
              "base_path": args.base_path, "mode": args.mode, "sse": args.sse,
              "h2": args.h2, "tools_enabled": args.tools_enabled, "model": args.model,
              "claude_version": subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip(),
              "agentsight_version": subprocess.run(["agentsight", "--version"], capture_output=True, text=True).stdout.strip(),
              "wrapped": wrapped, "detached": detached,
              "interpretation_rule": "If mock receives prompt but llm_calls stays zero, loss precedes the DB LLM record; do not infer the exact BPF/decoder stage without raw SSL evidence."}
    save(output / "summary.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if any(item and item["prompt_reached_mock"] for item in (wrapped, detached)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
