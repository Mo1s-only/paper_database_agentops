#!/usr/bin/env python3
"""Loopback-only controller for bounded thesis experiments.

This is intentionally not a general shell runner. The browser can select only
catalogued inputs; paid execution is limited to the already-authorized batch.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import threading
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4


SITE = Path(__file__).resolve().parents[1]
REPO = SITE.parents[1]
DIST = SITE / "dist"
RECORD_DIR = REPO / "lab/experiment/experiment_20261019_18"
RUN_DIR = RECORD_DIR / "results"
MANIFEST = REPO / "my_paper_coding/experiment_control/real-api-error-agentrx-20261019.json"
LEDGER = REPO / "my_paper_coding/experiment_control/cost-ledger-20261012-sse-clock.json"
LIVE_SCRIPT = REPO / "my_paper_coding/trace_adapter/capture_real_scenarios.py"
AGENTRX_SCRIPT = REPO / "my_paper_coding/experiment_control/run_agentrx_small_probe.py"
CREDENTIAL_FILE = REPO.parent / "agentsight/test/.env"
PAID_DATASET = "error-propagation-v1"
OFFLINE_MODES = {"adapter_compatibility", "synthetic_stress"}


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def linux_path(path: Path) -> str:
    resolved = path.resolve()
    if os.name != "nt" or not resolved.drive:
        return str(resolved)
    return "/mnt/" + resolved.drive[0].lower() + resolved.as_posix()[2:]


def command_probe(command: list[str], timeout: int = 8) -> tuple[bool, str]:
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, type(error).__name__
    return result.returncode == 0, str(result.returncode)


def gate(key: str, ok: bool, detail: str) -> dict:
    return {"key": key, "ok": bool(ok), "detail": detail}


def frozen_ledger_override_allowed(manifest: dict, ledger: dict) -> bool:
    """Permit only the explicitly approved frozen baseline for this one batch."""
    approval = manifest.get("historical_ledger_override")
    if not isinstance(approval, dict) or approval.get("approved_by_user") is not True:
        return False
    try:
        return (approval.get("batch_id") == manifest["batch_id"]
                and approval.get("approval_reply") == "是，按冻结账本继续启动"
                and approval.get("historical_cost_status") == "UNVERIFIED_RAW_LOGS"
                and approval.get("raw_log_paths_expected") == len(ledger["entries"]) == 30
                and abs(float(approval["baseline_total_usd"]) - float(ledger["total_cost_usd"])) < 0.000001
                and abs(float(approval["max_incremental_cny"]) - float(manifest["batch_cap_cny"])) < 0.000001)
    except (KeyError, TypeError, ValueError):
        return False


class ExperimentController:
    def __init__(self):
        self.lock = threading.RLock()
        self.active_run: str | None = None
        self.stop_after_current = False
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        for path in RUN_DIR.glob("run-*/state.json"):
            try:
                state = read_json(path)
                if state.get("status") == "RUNNING":
                    state["status"] = "INTERRUPTED"
                    state["stage"] = "CONTROLLER_RESTARTED"
                    state["finished_at"] = now()
                    state.setdefault("events", []).append({"at": now(), "stage": "CONTROLLER_RESTARTED",
                                                           "message": "控制器重启；此前 API 是否已调用、费用是否完整均需人工核对，不自动重试。"})
                    write_json(path, state)
            except (OSError, json.JSONDecodeError):
                continue

    def catalog(self) -> dict[str, dict]:
        return {item["id"]: item for item in read_json(DIST / "data.json")["datasetCatalog"]}

    def preflight(self, dataset_id: str) -> dict:
        dataset = self.catalog().get(dataset_id)
        if dataset is None:
            return {"dataset_id": dataset_id, "can_start": False,
                    "gates": [gate("dataset", False, "数据集不在受控目录中。")], "kind": "unknown"}
        input_file = (REPO / dataset["inputPath"]).resolve()
        try:
            input_file.relative_to(REPO.resolve())
            safe_path = True
        except ValueError:
            safe_path = False
        gates = [gate("input", safe_path and input_file.is_file(),
                      "本地输入存在且位于论文工作区内。" if safe_path and input_file.is_file() else "输入文件不可用。")]
        if dataset["mode"] in OFFLINE_MODES:
            kind = "offline_input_audit"
            gates.append(gate("scope", True, "仅复核已有标准化输入，不重新执行上游 adapter，也不调用 API。"))
        elif dataset_id == PAID_DATASET:
            kind = "authorized_live_batch"
            earlier_paid = any(
                read_json(path).get("kind") == "authorized_live_batch"
                for path in RUN_DIR.glob("run-*/state.json")
            )
            gates.append(gate("one_authorized_batch", not earlier_paid,
                              "当前授权批次尚未启动过。" if not earlier_paid else "该授权批次已有运行记录；禁止再次付费启动或自动重试。"))
            try:
                manifest, ledger = read_json(MANIFEST), read_json(LEDGER)
                baseline = float(manifest["baseline_ledger_total_usd"])
                current = float(ledger["total_cost_usd"])
                plan_usd = float(manifest["planned_batch_budget_usd"])
                plan_cny = float(manifest["planned_batch_budget_cny"])
                cap_cny = float(manifest["batch_cap_cny"])
                budget_ok = (abs(baseline - current) < 0.000001 and plan_cny < cap_cny
                             and current + plan_usd <= float(manifest["hard_stop_total_usd"]) + 1e-9)
                gates.append(gate("budget", budget_ok,
                                  f"冻结基线 ${current:.6f}；本批次规划 ¥{plan_cny:.2f}，上限 ¥{cap_cny:.2f}。"))
                entries = ledger.get("entries", [])
                present = sum((REPO / item["path"]).is_file() for item in entries)
                raw_complete = bool(entries) and present == len(entries)
                frozen_approved = frozen_ledger_override_allowed(manifest, ledger)
                detail = (f"历史费用原始记录可核对 {present}/{len(entries)}。" if raw_complete else
                          f"历史费用原始记录可核对 {present}/{len(entries)}；用户仅为本批次明确批准按冻结账本 ${current:.6f} 启动，历史费用仍未完全复核。"
                          if frozen_approved else
                          f"历史费用原始记录可核对 {present}/{len(entries)}；不可用时禁止付费调用。")
                gates.append(gate("ledger_evidence", raw_complete or frozen_approved, detail))
            except (OSError, KeyError, ValueError, json.JSONDecodeError):
                gates.append(gate("budget", False, "预算 manifest 或冻结账本不可读取。"))
            distro_ok, _ = command_probe(["wsl.exe", "-d", "Ubuntu", "-u", "root", "--exec", "/bin/true"])
            gates.append(gate("wsl_ubuntu", distro_ok, "Ubuntu WSL root 可进入。" if distro_ok else "未能进入 Ubuntu WSL root；当前不能采集 eBPF。"))
            if distro_ok:
                probe = ("command -v claude >/dev/null && command -v agentsight >/dev/null && "
                         "command -v python3 >/dev/null && test -e /sys/kernel/tracing && "
                         f"test -f {shlex.quote(linux_path(CREDENTIAL_FILE))} && "
                         f"set -a && . {shlex.quote(linux_path(CREDENTIAL_FILE))} && set +a && "
                         "{ test -n \"${ANTHROPIC_AUTH_TOKEN:-}\" || test -n \"${ANTHROPIC_API_KEY:-}\"; }")
                tools_ok, _ = command_probe(["wsl.exe", "-d", "Ubuntu", "-u", "root", "--exec", "/bin/bash", "-lc", probe])
                gates.append(gate("runtime", tools_ok, "CLI、AgentSight、Python、tracing 与本机已有凭据文件可用。" if tools_ok else "CLI、AgentSight、tracing 或本机凭据文件缺失；不读取或展示密钥值。"))
                path_ok, _ = command_probe(["wsl.exe", "-d", "Ubuntu", "-u", "root", "--exec", "test", "-f", linux_path(LIVE_SCRIPT)])
                gates.append(gate("wsl_workspace", path_ok, "WSL 可访问论文代码。" if path_ok else "WSL 无法访问论文代码路径。"))
            else:
                gates += [gate("runtime", False, "待 Ubuntu WSL 可进入后检查。"),
                          gate("wsl_workspace", False, "待 Ubuntu WSL 可进入后检查。")]
        else:
            kind = "not_authorized"
            gates.append(gate("scope", False, "本轮真实 API 授权只覆盖 error-propagation-v1 → AgentRx #12 的顺序批次。"))
        with self.lock:
            busy = self.active_run is not None
        gates.append(gate("single_run", not busy, "没有其他实验正在执行。" if not busy else "另一实验正在执行，请等待。"))
        return {"dataset_id": dataset_id, "kind": kind, "can_start": all(x["ok"] for x in gates),
                "gates": gates, "checked_at": now(), "api_required": bool(dataset["apiRequired"])}

    def state(self, run_id: str) -> dict | None:
        if not run_id.startswith("run-") or len(run_id) != 16 or any(c not in "0123456789abcdef" for c in run_id[4:]):
            return None
        path = RUN_DIR / run_id / "state.json"
        return read_json(path) if path.is_file() else None

    def list_runs(self) -> list[dict]:
        result = []
        for path in sorted(RUN_DIR.glob("run-*/state.json"), reverse=True)[:30]:
            try:
                state = read_json(path)
                result.append({key: state.get(key) for key in ("run_id", "name", "dataset_id", "kind", "status", "stage", "created_at", "finished_at")})
            except (OSError, json.JSONDecodeError):
                continue
        return result

    def start(self, name: str, dataset_id: str, confirm_budget: bool) -> tuple[int, dict]:
        name = name.strip()
        if not name or len(name) > 80:
            return 400, {"error": "请提供 1–80 字的实验名称。"}
        with self.lock:
            check = self.preflight(dataset_id)
            if not check["can_start"]:
                return 409, {"error": "预检未通过，实验未启动。", "preflight": check}
            if check["api_required"] and not confirm_budget:
                return 400, {"error": "真实 API 批次必须明确确认 2 元上限。"}
            run_id = "run-" + uuid4().hex[:12]
            folder = RUN_DIR / run_id
            folder.mkdir(parents=True, exist_ok=False)
            state = {"run_id": run_id, "name": name, "dataset_id": dataset_id,
                     "kind": check["kind"], "status": "RUNNING", "stage": "QUEUED",
                     "created_at": now(), "finished_at": None, "events": [],
                     "preflight": check, "result": None, "api_calls_confirmed": 0}
            write_json(folder / "state.json", state)
            self.active_run = run_id
            self.stop_after_current = False
            threading.Thread(target=self._work, args=(run_id,), daemon=True).start()
            return 201, {"run_id": run_id, "status": "RUNNING"}

    def _update(self, run_id: str, stage: str, message: str, **fields) -> dict:
        with self.lock:
            path = RUN_DIR / run_id / "state.json"
            state = read_json(path)
            state["stage"] = stage
            state["events"].append({"at": now(), "stage": stage, "message": message})
            state.update(fields)
            write_json(path, state)
            return state

    def stop_followup(self, run_id: str) -> tuple[int, dict]:
        with self.lock:
            if self.active_run != run_id:
                return 409, {"error": "该实验没有正在执行的后续阶段。"}
            state = self.state(run_id)
            if state is None or state["kind"] != "authorized_live_batch" or state["stage"] in {"AGENTRX", "FINISHED"}:
                return 409, {"error": "当前阶段没有可停止的后续 API 调用。"}
            self.stop_after_current = True
            self._update(run_id, "STOP_REQUESTED", "当前 API 会话不会被中断；本阶段结束后不再启动后续 API 阶段。")
            return 200, {"run_id": run_id, "stop_after_current": True}

    def continue_agentrx(self, run_id: str, confirm_budget: bool) -> tuple[int, dict]:
        """Finish the unattempted third call when only system capture failed.

        This is a continuation of the original three-call authorization, never
        a retry of either completed CLI session or of an attempted AgentRx call.
        """
        with self.lock:
            state = self.state(run_id)
            if (not confirm_budget or self.active_run is not None or state is None
                    or state.get("kind") != "authorized_live_batch" or state.get("status") != "FAILED"
                    or state.get("result", {}).get("failed_stage") != "error_propagation"
                    or state.get("result", {}).get("api_calls") != 2):
                return 409, {"error": "仅可继续已完成两会话且尚未调用 AgentRx 的授权批次；必须再次确认预算。"}
            folder = RUN_DIR / run_id
            if (folder / "agentrx-tau12").exists():
                return 409, {"error": "AgentRx 已有执行工件；禁止重复付费调用。"}
            try:
                manifest, ledger = read_json(MANIFEST), read_json(LEDGER)
                summary = read_json(folder / "error-propagation/capture-summary.json")
                plan = read_json(folder / "error-propagation/plan.json")
                agents = summary.get("agents", [])
                error_cost = float(summary["reported_cost_usd"])
                probe_cap = float(manifest["agentrx_max_usd"])
                rate = float(manifest["planning_usd_cny_rate"])
                valid = (frozen_ledger_override_allowed(manifest, ledger)
                         and plan.get("scenario") == PAID_DATASET
                         and float(plan["per_session_budget_usd"]) <= float(manifest["error_propagation_max_usd_per_session"])
                         and summary.get("actual_cli_sessions") == len(agents) == 2
                         and summary.get("cost_complete") is True
                         and summary.get("cost_cap_status") == "within_cap"
                         and all(agent.get("success") for agent in agents)
                         and error_cost >= 0 and (error_cost + probe_cap) * rate < float(manifest["batch_cap_cny"])
                         and float(ledger["total_cost_usd"]) + error_cost + probe_cap
                         <= float(manifest["hard_stop_total_usd"]) + 1e-9)
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                valid = False
            if not valid:
                return 409, {"error": "前序两会话或剩余预算未通过复核；AgentRx 未启动。"}
            state["previous_result"] = state["result"]
            state["result"] = None
            state["status"] = "RUNNING"
            state["stage"] = "AGENTRX_QUEUED"
            state["finished_at"] = None
            state["events"].append({"at": now(), "stage": "AGENTRX_QUEUED",
                                    "message": "前序两会话成功且费用完整；系统工具捕获不完整，仅继续尚未执行的 AgentRx 单次诊断。"})
            write_json(folder / "state.json", state)
            self.active_run = run_id
            threading.Thread(target=self._continue_agentrx_work, args=(run_id,), daemon=True).start()
            return 202, {"run_id": run_id, "status": "RUNNING", "stage": "AGENTRX_QUEUED"}

    def _continue_agentrx_work(self, run_id: str) -> None:
        try:
            folder = RUN_DIR / run_id
            error_output = folder / "error-propagation"
            agentrx_output = folder / "agentrx-tau12"
            self._update(run_id, "AGENTRX", "启动一条 AgentRx 真实诊断；不重跑前序两会话，单次限 $0.08。")
            code = self._wsl_run(AGENTRX_SCRIPT, ["--execute", "--error-run", linux_path(error_output),
                                                   "--output", linux_path(agentrx_output)], 300)
            prediction_path = agentrx_output / "prediction.json"
            score_path = agentrx_output / "score.json"
            if not prediction_path.is_file() or not score_path.is_file():
                result = {"status": "FAILED", "failed_stage": "agentrx", "exit_code": code,
                          "api_calls": "2 plus unknown", "note": "AgentRx 输出或费用不完整；不自动重试。"}
            else:
                prediction, score = read_json(prediction_path), read_json(score_path)
                result = {"status": "PARTIAL" if code == 0 else "FAILED", "api_calls": 3,
                          "error_reported_cost_usd": read_json(error_output / "capture-summary.json")["reported_cost_usd"],
                          "agentrx_reported_cost_usd": prediction.get("reported_cost_usd"),
                          "combined_cny_at_planning_rate": score.get("reported_total_cny_at_rate"),
                          "agentrx_step_exact": score.get("step_exact"),
                          "system_capture_status": "incomplete",
                          "note": "真实批次部分完成：前序原生事件与 AgentRx 诊断可评估，但 AgentSight 工具记录缺失；不得声称系统层归因成功。"}
            status = result.pop("status")
            self._update(run_id, "FINISHED", "授权批次结束；不再发起 API 调用。",
                         status=status, result=result, finished_at=now(),
                         api_calls_confirmed=3 if result.get("api_calls") == 3 else 2)
        except Exception as error:
            self._update(run_id, "FINISHED", f"AgentRx 运行器失败：{type(error).__name__}；不自动重试。",
                         status="FAILED", finished_at=now())
        finally:
            with self.lock:
                self.active_run = None

    def _work(self, run_id: str) -> None:
        try:
            state = self.state(run_id)
            if state["kind"] == "offline_input_audit":
                result = self._audit_input(run_id, state["dataset_id"])
            else:
                result = self._run_live_batch(run_id)
            status = result.pop("status", "COMPLETED")
            self._update(run_id, "FINISHED", "实验阶段结束；结果已保存。",
                         status=status, result=result, finished_at=now())
        except Exception as error:  # Never expose CLI output or secrets in the browser.
            self._update(run_id, "FINISHED", f"运行器失败：{type(error).__name__}。检查本地工件。",
                         status="FAILED", finished_at=now())
        finally:
            with self.lock:
                self.active_run = None
                self.stop_after_current = False

    def _audit_input(self, run_id: str, dataset_id: str) -> dict:
        dataset = self.catalog()[dataset_id]
        source = (REPO / dataset["inputPath"]).resolve()
        self._update(run_id, "INPUT_AUDIT", "读取已有标准化记录；不调用 API、不重新运行上游 adapter。")
        count = 0
        ids = set()
        invalid = []
        with source.open("r", encoding="utf-8") as stream:
            for line_no, line in enumerate(stream, 1):
                try:
                    row = json.loads(line)
                    if dataset["mode"] == "adapter_compatibility":
                        assert row.get("schema_version") == "attribution-benchmark-record-v0.1"
                        assert isinstance(row.get("steps"), list) and isinstance(row.get("relations"), list)
                        assert isinstance(row.get("provenance", {}).get("source_records"), list)
                        record_id = row["run"]["run_id"]
                    else:
                        assert row.get("evidence_kind") == "synthetic_fixture"
                        assert row.get("expected_status") in {"accepted", "uncertain", "abstain"}
                        record_id = row["fixture_id"]
                    assert record_id not in ids
                    ids.add(record_id)
                    count += 1
                except (AssertionError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                    invalid.append(line_no)
        result = {"source": dataset["inputPath"], "expected_records": dataset["recordCount"],
                  "parsed_records": count, "invalid_lines": invalid[:20],
                  "source_type": "existing_normalized_input", "api_calls": 0,
                  "scope": "输入结构复核；不是上游 adapter 重跑、系统侧捕获率或归因准确率"}
        write_json(RUN_DIR / run_id / "input-audit.json", result)
        artifact = RUN_DIR / run_id / "input-audit.json"
        try:
            result["artifact"] = str(artifact.relative_to(REPO))
        except ValueError:
            result["artifact"] = str(artifact)
        result["status"] = "COMPLETED" if not invalid and count == dataset["recordCount"] else "FAILED"
        return result

    def _wsl_run(self, script: Path, args: list[str], timeout: int) -> int:
        # The credential file remains outside the thesis repo and is never
        # passed through argv, HTTP responses, or captured stdout/stderr.
        arguments = " ".join(shlex.quote(part) for part in [linux_path(script), *args])
        shell_command = (f"set -a; . {shlex.quote(linux_path(CREDENTIAL_FILE))}; set +a; "
                         f"exec python3 {arguments}")
        command = ["wsl.exe", "-d", "Ubuntu", "-u", "root", "--exec", "/bin/bash", "-lc", shell_command]
        return subprocess.run(command, capture_output=True, timeout=timeout, check=False).returncode

    def _run_live_batch(self, run_id: str) -> dict:
        folder = RUN_DIR / run_id
        error_output = folder / "error-propagation"
        self._update(run_id, "ERROR_PROPAGATION", "启动双 Agent 真实场景；两次 CLI 会话各限 $0.05。")
        code = self._wsl_run(LIVE_SCRIPT, ["--scenario", PAID_DATASET, "--output", linux_path(error_output),
                                         "--per-session-budget", "0.05", "--experiment-cost-cap-cny", "1.0",
                                         "--planning-usd-cny-rate", "10", "--cumulative-manifest", linux_path(MANIFEST),
                                         "--cumulative-ledger", linux_path(LEDGER)], 900)
        summary_path = error_output / "capture-summary.json"
        if not summary_path.is_file():
            return {"status": "FAILED", "failed_stage": "error_propagation", "exit_code": code,
                    "api_calls": "unknown", "note": "缺少采集摘要；不得按零费用或成功处理。"}
        summary = read_json(summary_path)
        agents = summary.get("agents", [])
        confirmed = len(agents)
        self._update(run_id, "ERROR_REVIEW", "已读取 CLI 费用及两会话摘要。", api_calls_confirmed=confirmed)
        if code != 0 or confirmed != 2 or not summary.get("cost_complete") or not all(a.get("success") for a in agents):
            return {"status": "FAILED", "failed_stage": "error_propagation", "exit_code": code,
                    "api_calls": confirmed, "reported_cost_usd": summary.get("reported_cost_usd"),
                    "note": "前序场景不完整；AgentRx 未启动，无自动重试。"}
        with self.lock:
            if self.stop_after_current:
                return {"status": "STOPPED", "api_calls": confirmed,
                        "reported_cost_usd": summary["reported_cost_usd"], "note": "按页面请求跳过 AgentRx。"}
            self._update(run_id, "AGENTRX", "启动一条 AgentRx 轨迹诊断；仅 traj 输入，单次限 $0.08。")
        agentrx_output = folder / "agentrx-tau12"
        code = self._wsl_run(AGENTRX_SCRIPT, ["--execute", "--error-run", linux_path(error_output),
                                              "--output", linux_path(agentrx_output)], 300)
        prediction_path = agentrx_output / "prediction.json"
        score_path = agentrx_output / "score.json"
        if not prediction_path.is_file() or not score_path.is_file():
            return {"status": "FAILED", "failed_stage": "agentrx", "exit_code": code,
                    "api_calls": "2 plus unknown", "note": "AgentRx 结果或费用不完整；检查本地工件。"}
        prediction, score = read_json(prediction_path), read_json(score_path)
        return {"status": "COMPLETED" if code == 0 else "FAILED", "api_calls": 3,
                "error_reported_cost_usd": summary["reported_cost_usd"],
                "agentrx_reported_cost_usd": prediction.get("reported_cost_usd"),
                "combined_cny_at_planning_rate": score.get("reported_total_cny_at_rate"),
                "agentrx_step_exact": score.get("step_exact"),
                "artifacts": [str(summary_path.relative_to(REPO)), str(prediction_path.relative_to(REPO)), str(score_path.relative_to(REPO))],
                "note": "CLI 报告费用与内部换算，不等于最终账单；AgentRx 无配套系统侧观测。"}


CONTROLLER = ExperimentController()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def _allowed(self) -> bool:
        host = self.headers.get("Host", "")
        return host in {"127.0.0.1:8766", "localhost:8766"}

    def _json(self, code: int, payload: dict | list) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._allowed():
            return self._json(403, {"error": "Loopback host only"})
        url = urlsplit(self.path)
        if url.path == "/api/health":
            return self._json(200, {"controller": "ready", "active_run": CONTROLLER.active_run, "at": now()})
        if url.path == "/api/preflight":
            dataset_id = parse_qs(url.query).get("dataset_id", [""])[0]
            return self._json(200, CONTROLLER.preflight(dataset_id))
        if url.path == "/api/runs":
            return self._json(200, CONTROLLER.list_runs())
        if url.path.startswith("/api/runs/"):
            state = CONTROLLER.state(url.path.removeprefix("/api/runs/"))
            return self._json(200, state) if state else self._json(404, {"error": "Run not found"})
        return super().do_GET()

    def do_POST(self):
        if not self._allowed() or self.headers.get("Origin") not in {None, "http://127.0.0.1:8766", "http://localhost:8766"} or self.headers.get("X-AgentOps-Control") != "1":
            return self._json(403, {"error": "Same-origin control request required"})
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self._json(415, {"error": "JSON required"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 4096:
                return self._json(413, {"error": "Request too large"})
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
        except (TypeError, ValueError, json.JSONDecodeError):
            return self._json(400, {"error": "Invalid JSON"})
        path = urlsplit(self.path).path
        if path == "/api/runs":
            code, response = CONTROLLER.start(str(payload.get("name", "")), str(payload.get("dataset_id", "")), payload.get("confirm_budget") is True)
            return self._json(code, response)
        if path.startswith("/api/runs/") and path.endswith("/stop-after-current"):
            run_id = path.removeprefix("/api/runs/").removesuffix("/stop-after-current")
            code, response = CONTROLLER.stop_followup(run_id)
            return self._json(code, response)
        if path.startswith("/api/runs/") and path.endswith("/continue-agentrx"):
            run_id = path.removeprefix("/api/runs/").removesuffix("/continue-agentrx")
            code, response = CONTROLLER.continue_agentrx(run_id, payload.get("confirm_budget") is True)
            return self._json(code, response)
        if path == "/api/refresh-snapshot":
            if CONTROLLER.active_run:
                return self._json(409, {"error": "请等待当前实验结束。"})
            result = subprocess.run([sys.executable, str(SITE / "scripts/build_data.py")], cwd=REPO, capture_output=True, timeout=60, check=False)
            return self._json(200 if result.returncode == 0 else 500,
                              {"ok": result.returncode == 0, "message": "数据快照已刷新。" if result.returncode == 0 else "快照刷新失败；请查看本地脚本。"})
        return self._json(404, {"error": "Unknown control route"})

    def log_message(self, format, *args):
        # Keep the terminal log free of request bodies and credentials.
        sys.stderr.write("[controller] " + format % args + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    if args.port != 8766:
        parser.error("Controller intentionally uses the fixed loopback port 8766")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"AgentOps local controller: http://127.0.0.1:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
