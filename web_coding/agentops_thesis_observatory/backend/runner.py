"""Bounded fixed experiment recipes, with durable evidence before and after execution.

This module never accepts a command, model, endpoint, credential or path from HTTP.
The live recipe reuses the collector and hook instrumentation verified by run45.
"""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import ExitStack, closing
import base64
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import threading
import time


REPO = Path(__file__).resolve().parents[3]
COLLECTOR = "lab/agentsight/source/thesis_adapter/collector/target/release/agentsight"
COLLECTOR_SHA256 = "caa48e699a31c73837c63e581dfab7c47daeddbf09369d5ec83bdcf4c6aa5a76"
TRACE = "my_paper_coding/trace_adapter"
MANIFEST = "my_paper_coding/experiment_control/real-two-scenarios-plan-20261010.json"
LEDGER = "my_paper_coding/experiment_control/cost-ledger-20261012-sse-clock.json"
LIVE_DATASETS = {"error-propagation-v1", "routing-error-v1"}
FINAL_STATUSES = {"completed", "partial", "failed", "interrupted", "stopped"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def linux_path(path: Path):
    value = str(path.resolve()).replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", value):
        return "/mnt/" + value[0].lower() + value[2:]
    return value


def safe_text(value, secrets=()):
    """Strip terminal controls and redact known secrets before any durable/public text."""
    text = str(value)
    for secret in secrets:
        if secret and len(secret) >= 4:
            text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"(?i)((?:api[_-]?key|auth[_-]?token|authorization|password)\s*[=:]\s*)(?:Bearer\s+)?[^\s\"',;]+", r"\1[REDACTED]", text)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{12,}\b", "[REDACTED]", text)
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    return "".join(c for c in text if c in "\n\t" or ord(c) >= 32).replace("\x00", "")


# Launch one capture in its own process group. A signal reaches capture's finally
# blocks, which close the independent Claude/record/debug process groups.
# The wrapper waits for this cleanup; no global pkill or distro shutdown is used.
LINUX_WRAPPER = r'''
import json, os, pathlib, signal, subprocess, sys
pidfile, script, *arguments = sys.argv[1:]
child = subprocess.Popen([sys.executable, script, *arguments], start_new_session=True)
pathlib.Path(pidfile).write_text(json.dumps({"pid":child.pid,"script":script,"arguments":arguments}))
def stop(sig, frame):
    if child.poll() is None:
        os.killpg(child.pid, signal.SIGINT)
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
raise SystemExit(child.wait())
'''

LINUX_STOP = r'''
import json, os, pathlib, signal, sys
pidfile, expected_script, expected_output = sys.argv[1:]
path = pathlib.Path(pidfile)
if not path.is_file():
    raise SystemExit(3)
record = json.loads(path.read_text())
pid = int(record["pid"])
cmdline = pathlib.Path(f"/proc/{pid}/cmdline")
if not cmdline.is_file():
    raise SystemExit(0)
parts = cmdline.read_bytes().decode(errors="replace").split("\0")
if expected_script not in parts or expected_output not in parts:
    raise SystemExit("Scoped stop refused: PID does not belong to this capture")
os.killpg(pid, signal.SIGINT)
'''


class Runner:
    def __init__(self, repository):
        self.repository = repository
        self.repo = Path(getattr(repository, "repo", REPO))
        self.lock = threading.RLock()
        self.active_run = None
        self.workers = {}
        self.processes = {}
        self.stop_flags = {}
        self.credential_file = self.repo.parent / "agentsight/test/.env"
        self.vault_file = self.repo / "my_paper_coding/experiment_control/.secrets/api_keys.dpapi.json"
        self.secrets = tuple(value for key, value in os.environ.items()
                             if any(word in key.upper() for word in ("TOKEN", "KEY", "PASSWORD")))
        if self.credential_file.is_file():
            # Read only for redaction. The trusted existing file is sourced inside WSL;
            # its values never cross argv, the API, lifecycle or invocation metadata.
            values = []
            for line in self.credential_file.read_text(encoding="utf-8-sig").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    key, value = line.split("=", 1)
                    if any(word in key.upper() for word in ("TOKEN", "KEY", "PASSWORD")):
                        values.append(value.strip().strip("'\""))
            self.secrets += tuple(values)
        for summary in repository.list_runs():
            if summary.get("status") not in {"queued", "running"}:
                continue
            row = repository.get_run(summary["id"])
            if row and (Path(row["root"]) / "invocation.json").is_file():
                self._update(row["id"], "interrupted", "平台进程重启；上次运行没有完整结束，调用和费用以已有工件为准。",
                             status="interrupted", finished_at=now(),
                             error={"stage": "controller_restart", "message": "平台重启，运行已中断；不会自动重复调用 API。", "exit_code": None})

    def _dataset(self, dataset_id):
        return next((row for row in self.repository.catalog() if row["id"] == dataset_id), None)

    def _source(self, dataset):
        path = Path(dataset.get("source_path", ""))
        return path if path.is_absolute() else self.repo / path

    def _update(self, run_id, stage, message, **fields):
        message = safe_text(message, self.secrets)
        self.repository.update(run_id, stage=stage, summary=message, **fields)
        self.repository.event(run_id, stage, message)

    def _wsl_command(self, shell):
        return ["wsl.exe", "-d", "Ubuntu", "-u", "root", "--exec", "/bin/bash", "-lc", shell]

    def _credential_metadata(self):
        """Read non-secret alias metadata; never return encrypted or plaintext keys."""
        entry = read_json(self.vault_file).get("entries", {}).get("test")
        if entry:
            return {"source": "windows_dpapi", "alias": "test", "provider": entry.get("provider"), "model": entry.get("model")}
        if os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"):
            return {"source": "inherited_environment", "model": os.environ.get("ANTHROPIC_MODEL")}
        return {"source": "legacy_env_file" if self.credential_file.is_file() else "wsl_environment"}

    def _process_environment(self):
        environment = os.environ.copy()
        environment["PYTHONUTF8"] = "1"
        environment["PYTHONIOENCODING"] = "utf-8"
        names = ["ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL"]
        current = [part for part in environment.get("WSLENV", "").split(":") if part and part.split("/")[0] not in names]
        current.extend(name + "/u" for name in names if environment.get(name))
        environment["WSLENV"] = ":".join(current)
        return environment

    def _credential_command(self, shell):
        metadata = self._credential_metadata()
        if metadata["source"] != "windows_dpapi":
            return self._wsl_command(shell)
        # Same CurrentUser DPAPI mechanism as api_key_vault.ps1. Its RunScenario
        # action pins a historical output location, so this bridge only performs
        # credential forwarding around our already-fixed platform command.
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        bridge = r'''
$ErrorActionPreference = 'Stop'
$vault = Get-Content -LiteralPath VAULT_PATH -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
$entry = $vault.entries['test']
if ($null -eq $entry -or $entry.provider -ne 'deepseek') { throw 'DPAPI alias test is missing or has an unsupported provider.' }
$bstr = [IntPtr]::Zero
try {
    $secureKey = ConvertTo-SecureString $entry.encrypted_key
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    if ($plainKey.Length -lt 8) { throw 'DPAPI alias test could not provide a valid credential.' }
    $env:DEEPSEEK_API_KEY = $plainKey
    $env:ANTHROPIC_AUTH_TOKEN = $plainKey
    Remove-Item Env:\ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
    $env:ANTHROPIC_BASE_URL = 'https://api.deepseek.com/anthropic'
    $env:ANTHROPIC_MODEL = [string]$entry.model
    $names = @('DEEPSEEK_API_KEY','ANTHROPIC_AUTH_TOKEN','ANTHROPIC_API_KEY','ANTHROPIC_BASE_URL','ANTHROPIC_MODEL')
    $forward = @($env:WSLENV -split ':' | Where-Object { $_ -and ($_ -split '/')[0] -notin $names })
    $forward += @('DEEPSEEK_API_KEY/u','ANTHROPIC_AUTH_TOKEN/u','ANTHROPIC_BASE_URL/u','ANTHROPIC_MODEL/u')
    $env:WSLENV = $forward -join ':'
    & wsl.exe -d Ubuntu -u root --exec /bin/bash -lc SHELL_COMMAND
    $exitCode = $LASTEXITCODE
}
finally {
    if ($bstr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    Remove-Item Env:\DEEPSEEK_API_KEY,Env:\ANTHROPIC_AUTH_TOKEN -ErrorAction SilentlyContinue
    $plainKey = $null
}
exit $exitCode
'''.replace("VAULT_PATH", quote(self.vault_file)).replace("SHELL_COMMAND", quote(shell))
        powershell = shutil.which("pwsh") or str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "PowerShell/7/pwsh.exe")
        return [powershell, "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(bridge.encode("utf-16-le")).decode("ascii")]

    def _probe(self, shell, timeout=20, credentials=False):
        try:
            command = self._credential_command(shell) if credentials else self._wsl_command(shell)
            result = subprocess.run(command, capture_output=True, timeout=timeout, check=False, env=self._process_environment())
            output = self._decode(result.stdout) + "\n" + self._decode(result.stderr)
            return result.returncode == 0, safe_text(output.strip(), self.secrets)[-2200:]
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, safe_text(exc, self.secrets)[:1000]

    @staticmethod
    def _decode(value):
        if isinstance(value, str):
            return value
        if value and b"\x00" in value[:100]:
            return value.decode("utf-16-le", errors="replace").lstrip("\ufeff")
        return (value or b"").decode("utf-8", errors="replace")

    def _credential_setup(self):
        prefix = "set -e; umask 077; export PATH=/usr/local/bin:/root/.local/bin:$PATH; "
        prefix += "export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1; "
        # The successful DPAPI bridge forwards valid credentials using WSLENV.
        # Never replace those with a stale .env or a test fixture credential.
        prefix += "if [ -z \"${ANTHROPIC_AUTH_TOKEN:-}${ANTHROPIC_API_KEY:-}\" ] && [ -n \"${DEEPSEEK_API_KEY:-}\" ]; then export ANTHROPIC_AUTH_TOKEN=\"$DEEPSEEK_API_KEY\"; export ANTHROPIC_BASE_URL=\"${ANTHROPIC_BASE_URL:-https://api.deepseek.com/anthropic}\"; fi; "
        if self.credential_file.is_file():
            prefix += "if [ -z \"${ANTHROPIC_AUTH_TOKEN:-}${ANTHROPIC_API_KEY:-}\" ]; then set -a; . " + shlex.quote(linux_path(self.credential_file)) + "; set +a; fi; "
        return prefix

    def preflight(self, dataset_id):
        dataset = self._dataset(dataset_id)
        checks = []
        def add(name, ok, detail):
            checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not dataset:
            return {"ok": False, "checks": [{"name": "dataset", "ok": False, "detail": "请选择已登记的数据集。"}], "api_required": False, "budget_usd": None}
        source = self._source(dataset)
        add("input", source.is_file(), "输入源文件存在，可在页面打开。" if source.is_file() else "登记的输入源文件不存在。")
        live = dataset_id in LIVE_DATASETS
        if live:
            collector = self.repo / COLLECTOR
            digest = hashlib.sha256(collector.read_bytes()).hexdigest() if collector.is_file() else None
            add("collector", digest == COLLECTOR_SHA256,
                "复用 10 月 22 日成功运行的源码构建采集器，SHA-256 一致。" if digest == COLLECTOR_SHA256 else "已验证的采集器不存在或哈希不一致；请恢复 run45 对应的源码构建文件。")
            add("budget_files", all((self.repo / value).is_file() for value in (MANIFEST, LEDGER)),
                "保留历史预算记录；按用户已授权的累计预算覆盖启动，每会话软上限 $0.05，两会话规划 $0.10。")
            wsl_ok, output = self._probe("test \"$(id -u)\" = 0 && command -v python3 >/dev/null && command -v claude >/dev/null && echo ubuntu-ready")
            add("wsl", wsl_ok, "Ubuntu WSL root、Python 和 Claude CLI 可用。" if wsl_ok else
                "无法进入 Ubuntu WSL 或缺少 CLI。请在 Windows 本机终端启动平台，确认 wsl -d Ubuntu -u root 可进入；权限拒绝时以管理员运行启动器。诊断：" + output[-700:])
            if wsl_ok:
                credential_check = self._credential_setup() + "test -n \"${ANTHROPIC_AUTH_TOKEN:-}${ANTHROPIC_API_KEY:-}\""
                credential_ok, diagnostic = self._probe(credential_check, credentials=True)
                metadata = self._credential_metadata()
                label = "DPAPI 别名 test（" + str(metadata.get("provider")) + " / " + str(metadata.get("model")) + "）" if metadata["source"] == "windows_dpapi" else metadata["source"]
                add("credential", credential_ok, "凭据来源：" + label + "；已检查解密与 WSL 转发，未向供应商发送请求。" if credential_ok else "凭据解密或 WSL 转发失败：" + diagnostic[-900:])
                # --help/version do not call a provider. Check actual runner and CLI
                # flags to catch version skew before a paid session is launched.
                help_code = (
                    "import pathlib,subprocess,sys; "
                    "s=subprocess.run([sys.executable,sys.argv[1],'--help'],capture_output=True,text=True); "
                    "c=subprocess.run(['claude','--help'],capture_output=True,text=True); "
                    "required=['--tool-id-bridge','--agentsight-bin','--expected-agentsight-sha256','--ignore-cumulative-budget']; "
                    "assert s.returncode==0 and all(x in s.stdout for x in required), 'capture runner flags mismatch'; "
                    "assert c.returncode==0 and all(x in c.stdout for x in ['--max-budget-usd','--include-hook-events','--setting-sources']), 'Claude CLI flags mismatch'; "
                    "assert pathlib.Path('/sys/kernel/btf/vmlinux').is_file(), 'kernel BTF missing'; "
                    "print('runner-and-cli-compatible')"
                )
                compatible, detail = self._probe("python3 -c " + shlex.quote(help_code) + " " + shlex.quote(linux_path(self.repo / TRACE / "capture_real_scenarios.py")))
                add("compatibility", compatible, "运行器参数、CLI 工具钩子和内核 BTF 已检查；预检不调用 API。" if compatible else "运行器或 CLI 版本不兼容：" + detail[-900:])
            else:
                add("credential", False, "WSL 可用后才能检查凭据。")
                add("compatibility", False, "WSL 可用后才能检查运行器版本。")
            with self.lock:
                add("single_live_run", self.active_run is None, "每次运行有独立目录，历史结果不限制重复实验。" if self.active_run is None else "已有真实实验运行中：" + self.active_run)
        return {"ok": all(item["ok"] for item in checks), "checks": checks,
                "api_required": live, "budget_usd": 0.1 if live else 0,
                "network_calls_made": 0, "checked_at": now()}

    def start(self, payload):
        dataset_id = str(payload.get("dataset_id", ""))
        dataset = self._dataset(dataset_id)
        if not dataset:
            return 400, {"error": "请选择已登记的数据集。"}
        name = str(payload.get("name", "")).strip()
        if not name or len(name) > 120:
            return 400, {"error": "实验名称须为 1–120 个字符。"}
        if payload.get("experiment_type") != dataset.get("experiment_type"):
            return 400, {"error": "实验类型与所选数据集不匹配。"}
        live = dataset_id in LIVE_DATASETS
        if bool(dataset.get("api_required")) != live:
            return 400, {"error": "此数据集没有固定运行配方。"}
        if live and payload.get("confirm_api") is not True:
            return 400, {"error": "请确认本次真实 API 调用：两次 CLI 会话，每会话软上限 $0.05。"}
        check = self.preflight(dataset_id)
        if not check["ok"]:
            return 409, {"error": "启动预检未通过；请处理未通过项。", "preflight": check}
        with self.lock:
            if live and self.active_run:
                return 409, {"error": "已有真实实验运行中，请等待结束。"}
            record = self.repository.new_run(name, dataset_id)
            run_id = record["id"]
            root = Path(record["root"])
            write_json(root / "invocation.json", {
                "platform": "agentops-observatory", "run_id": run_id, "dataset_id": dataset_id,
                "created_at": now(), "experiment_type": dataset["experiment_type"],
                "recipe": "run45-source-collector-and-tool-id-bridge" if live else "local-input-structure-audit",
                "api_required": live, "api_confirmed": live,
                "planned_cli_sessions": 2 if live else 0, "per_session_soft_cap_usd": 0.05 if live else 0,
                "planned_budget_usd": 0.1 if live else 0,
                "cumulative_budget_override": {"enabled": live, "reason": "用户在本会话明确授权覆盖旧累计上限以测试真实 API；保留逐会话限制与独立运行记录。"},
                "collector_sha256": COLLECTOR_SHA256 if live else None,
                "tool_id_bridge": live, "automatic_rerun": False, "preflight": check,
                "credential_source": self._credential_metadata() if live else None,
                "cost_scope": "CLI soft caps and reported usage; not a provider hard cap or final invoice"})
            self.repository.update(run_id, status="queued", source_kind="platform", experiment_type=dataset["experiment_type"], preflight=check)
            self.repository.event(run_id, "queued", "创建独立运行目录；等待执行。")
            self.stop_flags[run_id] = threading.Event()
            if live:
                self.active_run = run_id
            worker = threading.Thread(target=self._work, args=(run_id, dataset, live), daemon=True, name=run_id)
            self.workers[run_id] = worker
            worker.start()
            return 202, {"id": run_id, "status": "queued", "message": "实验已创建，可查看本次运行进度。"}

    def _work(self, run_id, dataset, live):
        root = Path(self.repository.get_run(run_id)["root"])
        try:
            self._update(run_id, "starting", "开始执行本次实验。", status="running")
            if self.stop_flags[run_id].is_set():
                self._finish(run_id, "stopped", "运行在启动前停止。")
            elif live:
                self._live(run_id, dataset, root)
            else:
                self._audit(run_id, dataset, root)
        except Exception as exc:
            error = {"stage": self.repository.get_run(run_id).get("stage", "runner"),
                     "message": safe_text(exc, self.secrets)[-1800:], "exit_code": None}
            write_json(root / "failure.json", error)
            self._finish(run_id, "stopped" if self.stop_flags[run_id].is_set() else "failed", error["message"], error=error)
        finally:
            try:
                self.finalize(run_id)
            except Exception as exc:
                self.repository.event(run_id, "report_error", "报告生成失败：" + safe_text(exc, self.secrets)[:500])
            with self.lock:
                if self.active_run == run_id:
                    self.active_run = None
                self.processes.pop(run_id, None)

    def _finish(self, run_id, status, summary, **fields):
        self._update(run_id, "finished", summary, status=status, finished_at=now(), **fields)

    def _run_process(self, run_id, command, root, stage, timeout):
        private = root / "private"
        private.mkdir(exist_ok=True)
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self._process_environment())
        with self.lock:
            self.processes[run_id] = process
        deadline = time.monotonic() + timeout
        readers = []
        tails = {"stdout": [], "stderr": []}
        def drain(stream, name):
            with (private / (stage + "-" + name + ".log")).open("w", encoding="utf-8") as target:
                while True:
                    chunk = stream.readline()
                    if not chunk:
                        break
                    cleaned = safe_text(self._decode(chunk), self.secrets)
                    target.write(cleaned); target.flush()
                    tails[name].append(cleaned)
                    if len(tails[name]) > 30:
                        tails[name].pop(0)
        for stream, name in ((process.stdout, "stdout"), (process.stderr, "stderr")):
            thread = threading.Thread(target=drain, args=(stream, name), daemon=True)
            thread.start(); readers.append(thread)
        timed_out = False
        last_stop_attempt = 0
        while process.poll() is None:
            if self.stop_flags[run_id].is_set():
                if stage == "capture" and time.monotonic() - last_stop_attempt > 2:
                    # A stop may race the first PID-file write. Retry a scoped
                    # signal until the bounded capture has actually exited.
                    last_stop_attempt = time.monotonic()
                    self._signal_capture(root)
                elif stage != "capture":
                    process.terminate()
            if time.monotonic() > deadline:
                timed_out = True
                if stage == "capture":
                    self._signal_capture(root)
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        process.terminate()
                else:
                    process.terminate()
                break
            time.sleep(0.25)
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=5)
        for thread in readers:
            thread.join(timeout=3)
        for stream in (process.stdout, process.stderr):
            stream.close()
        return {"exit_code": process.returncode, "timed_out": timed_out,
                "stderr_tail": "".join(tails["stderr"])[-1800:],
                "stdout_tail": "".join(tails["stdout"])[-600:]}

    def _live(self, run_id, dataset, root):
        output = root / "capture"
        script = self.repo / TRACE / "capture_real_scenarios.py"
        arguments = ["--scenario", dataset["id"], "--output", linux_path(output),
                     "--agentsight-bin", linux_path(self.repo / COLLECTOR),
                     "--expected-agentsight-sha256", COLLECTOR_SHA256,
                     "--per-session-budget", "0.05", "--experiment-cost-cap-cny", "2.0",
                     "--planning-usd-cny-rate", "10", "--cumulative-manifest", linux_path(self.repo / MANIFEST),
                     "--cumulative-ledger", linux_path(self.repo / LEDGER),
                     "--ignore-cumulative-budget", "--tool-id-bridge"]
        private = root / "private"
        private.mkdir(exist_ok=True)
        command = ["python3", "-c", LINUX_WRAPPER, linux_path(private / "capture-process.json"), linux_path(script), *arguments]
        invocation = read_json(root / "invocation.json")
        invocation["fixed_argv"] = ["python3", linux_path(script), *arguments]
        write_json(root / "invocation.json", invocation)
        self._update(run_id, "capture", "Ubuntu WSL 采集器与两个 Agent 会话已启动；API 调用以本次会话摘要为准。")
        result = self._run_process(run_id, self._credential_command(self._credential_setup() + "exec " + shlex.join(command)), root, "capture", 420)
        summary = read_json(output / "capture-summary.json")
        agents = summary.get("agents", [])
        if self.stop_flags[run_id].is_set():
            self._finish(run_id, "stopped", "已停止本次运行；保留已有调用和采集工件，费用缺失时为未知。")
            return
        if not summary:
            http_diagnostic = self._http_failure(output)
            message = ("采集未生成会话摘要，API 调用和费用未知。" +
                       ("运行超时。" if result["timed_out"] else "") +
                       " 运行器诊断：" + (http_diagnostic or self._public_process_error(result) or "无输出，检查 WSL 启动权限。"))
            error = {"stage": "capture", "message": message, "exit_code": result["exit_code"]}
            write_json(root / "failure.json", error)
            self._finish(run_id, "failed", message, error=error)
            return
        self._update(run_id, "postprocess", "正在解析本次原生工具事件、SQLite 和跨层关联；此阶段不调用 API。")
        parse_agents = [agent["agent_id"] for agent in agents
                        if agent.get("success") and (output / (agent["agent_id"] + "-launch.json")).is_file()]
        post_errors = []
        task_outputs = self._task_outputs(dataset["id"], output)
        missing_outputs = task_outputs["missing_outputs"]
        if parse_agents and (output / "session.db").is_file():
            post_commands = [
                ("parse_native", "parse_claude_native.py", ["--run", str(output), "--output", str(output / "parsed"), "--agents", *parse_agents]),
                ("align", "prepare_real_alignment.py", ["--run", str(output)]),
            ]
            if len(parse_agents) == 2 and not missing_outputs:
                post_commands.append(("scenario_check", "validate_real_scenarios.py", ["--run", str(output)]))
            for stage, filename, args in post_commands:
                if self.stop_flags[run_id].is_set():
                    self._finish(run_id, "stopped", "已停止后处理，已有原始工件保留。")
                    return
                self.repository.event(run_id, stage, {"parse_native": "转换原生工具 Trace。", "align": "计算独立身份关联与受控进程桥接。", "scenario_check": "计算本场景确定性输出核对。"}[stage])
                post = self._run_process(run_id, [sys.executable, str(self.repo / TRACE / filename), *args], root, stage, 120)
                if post["exit_code"] != 0:
                    post_errors.append({"stage": stage, "message": self._public_process_error(post), "exit_code": post["exit_code"]})
                    break
                if stage == "scenario_check":
                    task_outputs.update(status="validated", scenario_score_available=(output / "scenario-score.json").is_file())
                    write_json(output / "scenario-validation-status.json", task_outputs)
        comparison = read_json(output / "alignment-inputs/real-alignment-comparison.json")
        accepted = comparison.get("identity_modes", {}).get("session-and-tool", {}).get("accepted", 0)
        good = (len(agents) == 2 and all(agent.get("success") for agent in agents)
                and summary.get("cost_complete") is True and result["exit_code"] == 0
                and comparison.get("native_tool_starts", 0) > 0
                and accepted == comparison.get("native_tool_starts") == comparison.get("system_tool_ids")
                and not post_errors and not missing_outputs)
        if good:
            self._finish(run_id, "completed", "两次真实 CLI 会话成功，原生与系统工具 ID 一致；详见本次关联模式与受控进程桥接证据。")
        else:
            http_diagnostic = self._http_failure(output)
            if not post_errors and len(parse_agents) == 2 and missing_outputs:
                error = self._task_output_error(summary, comparison, task_outputs)
            else:
                error = post_errors[0] if post_errors else {
                "stage": "capture" if result["exit_code"] else "correlation",
                "message": (http_diagnostic or self._public_process_error(result) or "会话、费用或跨层覆盖未满足完整条件；请查看已有工件。"),
                "exit_code": result["exit_code"]}
            write_json(root / "failure.json", error)
            successful = any(agent.get("success") for agent in agents)
            self._finish(run_id, "partial" if successful else "failed", error["message"] if not successful or error["stage"] == "task_output" else "本次已保留部分观测，完整性仍有缺口。", error=error)

    @staticmethod
    def _public_process_error(result):
        # Full sanitized diagnostics are retained privately. Show only the final
        # exception/error line rather than leaking a Python stack into the UI.
        text = result.get("stderr_tail") or result.get("stdout_tail") or ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return lines[-1][:900] if lines else ""

    @staticmethod
    def _task_outputs(dataset_id, output):
        expected = {"error-propagation-v1": ["handoff.json", "decision.json"],
                    "routing-error-v1": ["route.json", "result.json"]}.get(dataset_id, [])
        missing = ["workspace/" + name for name in expected if not (output / "workspace" / name).is_file()]
        status = {"dataset_id": dataset_id, "status": "incomplete_task_outputs" if missing else "outputs_present",
                  "expected_outputs": ["workspace/" + name for name in expected], "missing_outputs": missing,
                  "scenario_score_available": False,
                  "scope": "Task artifact presence only; does not change actual API session or native/system tool counts."}
        write_json(output / "scenario-validation-status.json", status)
        return status

    @staticmethod
    def _task_output_error(summary, comparison, status):
        agents = summary.get("agents", [])
        successes = sum(agent.get("success") is True for agent in agents)
        native, system = comparison.get("native_tool_starts"), comparison.get("system_tool_ids")
        accepted = comparison.get("identity_modes", {}).get("session-and-tool", {}).get("accepted")
        show = lambda value: "未知" if value is None else str(value)
        message = (f"API 会话成功 {successes}/{len(agents)}；实际原生/系统工具 {show(native)}/{show(system)}，"
                   f"session-and-tool accepted {show(accepted)}。缺少任务输出：{', '.join(status['missing_outputs'])}；场景评分未执行。")
        return {"stage": "task_output", "message": message, "exit_code": None}

    def refresh_task_output_diagnosis(self, run_id):
        """Reclassify an existing completed capture without executing any model call."""
        record = self.repository.get_run(run_id)
        if not record or record.get("status") not in FINAL_STATUSES:
            raise ValueError("Only a finished platform run can be reclassified")
        root = Path(record["root"])
        output = root / "capture"
        summary = read_json(output / "capture-summary.json")
        comparison = read_json(output / "alignment-inputs/real-alignment-comparison.json")
        status = self._task_outputs(record.get("dataset_id"), output)
        if status["missing_outputs"] and len(summary.get("agents", [])) == 2 and all(agent.get("success") for agent in summary["agents"]):
            error = self._task_output_error(summary, comparison, status)
            write_json(root / "failure.json", error)
            self.repository.update(run_id, status="partial", summary=error["message"], error=error)
            self.repository.event(run_id, "task_output_review", error["message"])
            self.finalize(run_id)
        return status

    @staticmethod
    def _http_failure(output):
        """Report observed response status, never return stored request/response bodies."""
        database = output / "session.db"
        if not database.is_file():
            return None
        try:
            with closing(sqlite3.connect("file:" + database.as_posix() + "?mode=ro", uri=True)) as connection:
                counts = connection.execute("SELECT status_code, count(*) FROM llm_calls WHERE status_code >= 400 GROUP BY status_code ORDER BY status_code").fetchall()
        except sqlite3.Error:
            return None
        if not counts:
            return None
        labels = {401: "认证失败，请核对当前凭据来源", 403: "供应商拒绝访问", 429: "供应商限流或配额不足"}
        messages = [f"HTTP {code}（{labels.get(code, '供应商请求失败')}）：SQLite 中 {count} 条观测" for code, count in counts]
        return "；".join(messages) + "。观测条数不等于独立计费请求数，费用按会话摘要核验。"

    def _audit(self, run_id, dataset, root):
        self._update(run_id, "audit", "逐条检查实际本地输入并写入独立 SQLite；此实验不访问外部 API。")
        source = self._source(dataset)
        sha = hashlib.sha256(source.read_bytes()).hexdigest()
        total = valid = invalid = 0
        errors = []
        with ExitStack() as stack:
            connection = stack.enter_context(closing(sqlite3.connect(root / "input.sqlite")))
            stack.enter_context(connection)
            connection.execute("CREATE TABLE input_records (record_no INTEGER PRIMARY KEY, source_line INTEGER, valid INTEGER, record_type TEXT, payload_json TEXT, error TEXT)")
            if source.suffix.lower() == ".jsonl":
                iterable = enumerate(stack.enter_context(source.open(encoding="utf-8-sig")), 1)
            else:
                value = json.loads(source.read_text(encoding="utf-8-sig"))
                iterable = enumerate(value if isinstance(value, list) else [value], 1)
            for line_no, value in iterable:
                if self.stop_flags[run_id].is_set():
                    self._finish(run_id, "stopped", "输入复核已停止；已处理记录保留。")
                    return
                if isinstance(value, str) and not value.strip():
                    continue
                total += 1
                error = None
                try:
                    row = json.loads(value) if isinstance(value, str) else value
                    if not isinstance(row, dict):
                        raise ValueError("记录不是 JSON 对象")
                    payload = json.dumps(row, ensure_ascii=False)
                    record_type = row.get("record_type") or row.get("event_type") or row.get("type") or "object"
                    valid += 1
                except (ValueError, TypeError) as exc:
                    row = None; payload = str(value); record_type = None
                    invalid += 1; error = str(exc)
                    if len(errors) < 10:
                        errors.append({"line": line_no, "message": error})
                connection.execute("INSERT INTO input_records VALUES (?,?,?,?,?,?)", (total, line_no, int(error is None), str(record_type) if record_type else None, payload, error))
            report = {"run_id": run_id, "dataset_id": dataset["id"], "source_path": str(source), "source_sha256": sha,
                      "network_calls_made": 0, "api_required": False, "total_records": total,
                      "valid_records": valid, "invalid_records": invalid, "errors": errors,
                      "scope": "Input JSON structure only; no live model call, runtime observation or cross-layer validation"}
            write_json(root / "audit-report.json", report)
        self._finish(run_id, "completed" if not invalid and total > 0 else "partial",
                     f"实际输入复核：{total} 条，结构有效 {valid} 条，异常 {invalid} 条；外部 API 调用 0。")

    def _signal_capture(self, root):
        command = ["python3", "-c", LINUX_STOP, linux_path(root / "private/capture-process.json"),
                   linux_path(self.repo / TRACE / "capture_real_scenarios.py"), linux_path(root / "capture")]
        return self._probe(shlex.join(command), timeout=12)

    def stop(self, run_id):
        with self.lock:
            flag = self.stop_flags.get(run_id)
            row = self.repository.get_run(run_id)
            if not row:
                return 404, {"error": "运行不存在。"}
            if not flag or row.get("status") in FINAL_STATUSES:
                return 409, {"error": "此运行当前没有可停止的任务。"}
            flag.set()
            process = self.processes.get(run_id)
            live = row.get("dataset_id") in LIVE_DATASETS
        self.repository.event(run_id, "stop_requested", "请求停止本次任务并保存已有证据。")
        if process and process.poll() is None:
            if live and row.get("stage") == "capture":
                ok, detail = self._signal_capture(Path(row["root"]))
                if not ok:
                    self.repository.event(run_id, "stop_pending", "停止信号未确认，等待本次有界任务退出：" + detail[-300:])
            else:
                process.terminate()
        return 202, {"id": run_id, "status": "stopping", "message": "已请求停止；页面将显示最终停止状态与已保存证据。"}

    def finalize(self, run_id):
        """Persist a useful analysis image for observed values; unknown stays unknown."""
        detail = self.repository.detail(run_id)
        if not detail:
            return
        root = Path(self.repository.get_run(run_id)["root"])
        api = detail.get("api", {})
        correlation = detail.get("correlation", {})
        counts = detail.get("database", {}).get("counts", {})
        report = {"run_id": run_id, "generated_at": now(), "status": detail.get("status"),
                  "dataset": detail.get("dataset"), "api": api, "correlation": correlation,
                  "table_counts": counts, "error": detail.get("error"),
                  "evidence_scope": "Metrics derived only from this run's files; unknown values are null."}
        write_json(root / "report.json", report)
        render = lambda value: "未知" if value is None else str(value)
        lines = [f"# {detail.get('name', run_id)}", "", f"运行：{run_id}", f"状态：{detail.get('status')}", "",
                 f"API：{api.get('label', api.get('status', '未知'))}", f"CLI 会话：{render(api.get('sessions'))}",
                 f"CLI 报告费用（USD）：{render(api.get('cost_usd'))}", "",
                 f"跨层关联：{correlation.get('label', correlation.get('status', '未知'))}",
                 f"原生工具 / 系统工具：{render(correlation.get('native_tools'))} / {render(correlation.get('system_tools'))}", "",
                 "| SQLite 表 | 实际行数 |", "| --- | ---: |"]
        lines.extend(f"| {name} | {render(value)} |" for name, value in sorted(counts.items()))
        if detail.get("error"):
            lines.extend(["", "## 运行诊断", "", safe_text(detail["error"].get("message", ""), self.secrets)])
        lines.extend(["", "受控工具 ID 进程桥接与通用 process-and-tool 分开报告。结构审计不证明真实 API 调用或跨层关联。", ""])
        (root / "report.md").write_text("\n".join(lines), encoding="utf-8")
        numeric = [(name, value) for name, value in counts.items() if isinstance(value, (int, float))]
        height = max(240, 125 + 32 * len(numeric))
        bars = []
        maximum = max([value for _, value in numeric] + [1])
        for index, (name, value) in enumerate(numeric):
            y = 100 + index * 32
            width = value / maximum * 470
            bars.append(f'<text x="24" y="{y + 15}" fill="#64748b" font-size="12">{html.escape(name)}</text><rect x="210" y="{y}" width="{width:.2f}" height="21" rx="4" fill="#0f766e"/><text x="{220 + width:.2f}" y="{y + 15}" font-size="12" fill="#0f172a">{value}</text>')
        if not numeric:
            bars.append('<text x="24" y="112" font-size="15" fill="#64748b">No SQLite observations available; values remain unknown.</text>')
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="780" height="{height}" viewBox="0 0 780 {height}" role="img" aria-label="Observed SQLite record counts"><rect width="780" height="{height}" fill="#f8fafc"/><text x="24" y="34" font-family="sans-serif" font-size="19" fill="#0f172a">{html.escape(run_id)} · SQLite records</text><text x="24" y="60" font-size="12" fill="#64748b">Actual per-run table counts; network rows do not imply API success or causality.</text>{"".join(bars)}</svg>'
        (root / "charts.svg").write_text(svg, encoding="utf-8")
        self.repository.event(run_id, "analysis_ready", "本次运行报告、原始表统计和图像已生成。")
