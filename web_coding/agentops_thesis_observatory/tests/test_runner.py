"""The launch boundary is tested without issuing any external API request."""
import json
import base64
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.data import Repository
from backend.runner import Runner, safe_text, COLLECTOR_SHA256


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repository = Repository(runtime_dir=self.root / "registry", run_root=self.root / "runs", discover=False)
        self.runner = Runner(self.repository)

    def tearDown(self):
        for worker in self.runner.workers.values():
            worker.join(timeout=5)
        self.temporary.cleanup()

    def wait(self, identifier):
        self.runner.workers[identifier].join(timeout=10)
        self.assertFalse(self.runner.workers[identifier].is_alive())
        return self.repository.detail(identifier)

    def test_repeat_input_audits_create_independent_real_sqlite_and_image(self):
        payload = {"name": "重复输入复核", "dataset_id": "alignment-stress-1000", "experiment_type": "input_audit"}
        code, first = self.runner.start(payload)
        self.assertEqual(code, 202)
        detail = self.wait(first["id"])
        root = Path(self.repository.get_run(first["id"])["root"])
        report = json.loads((root / "audit-report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["network_calls_made"], 0)
        self.assertEqual(report["total_records"], 1000)
        with closing(sqlite3.connect(root / "input.sqlite")) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM input_records").fetchone()[0], 1000)
        self.assertEqual(detail["status"], "completed")
        self.assertTrue((root / "charts.svg").is_file())
        code, second = self.runner.start(payload)
        self.assertEqual(code, 202)
        self.wait(second["id"])
        self.assertNotEqual(first["id"], second["id"])

    def test_failed_launch_preserves_unknown_api_and_exact_bounded_recipe(self):
        commands = []
        def failed(run_id, command, root, stage, timeout):
            commands.append(command)
            return {"exit_code": 2, "timed_out": False, "stderr_tail": "argument check failed before summary", "stdout_tail": ""}
        payload = {"name": "live launch failure", "dataset_id": "error-propagation-v1", "experiment_type": "cross_layer_live", "confirm_api": True}
        with patch.object(self.runner, "preflight", return_value={"ok": True, "checks": []}), patch.object(self.runner, "_run_process", side_effect=failed):
            code, response = self.runner.start(payload)
            self.assertEqual(code, 202)
            detail = self.wait(response["id"])
        root = Path(self.repository.get_run(response["id"])["root"])
        invocation = json.loads((root / "invocation.json").read_text(encoding="utf-8"))
        self.assertIn("--tool-id-bridge", invocation["fixed_argv"])
        self.assertIn("--ignore-cumulative-budget", invocation["fixed_argv"])
        self.assertIn(COLLECTOR_SHA256, invocation["fixed_argv"])
        self.assertEqual(invocation["per_session_soft_cap_usd"], 0.05)
        self.assertEqual(detail["status"], "failed")
        self.assertIsNone(detail["api"]["sessions"])
        self.assertIn("argument check failed", detail["error"]["message"])
        self.assertTrue((root / "failure.json").exists())
        self.assertIsNone(self.runner.active_run)

    def test_live_start_requires_per_run_confirmation_and_matching_type(self):
        payload = {"name": "repeat", "dataset_id": "error-propagation-v1", "experiment_type": "cross_layer_live"}
        self.assertEqual(self.runner.start(payload)[0], 400)
        payload.update(confirm_api=True, experiment_type="input_audit")
        self.assertEqual(self.runner.start(payload)[0], 400)
        self.assertEqual(self.repository.list_runs(), [])

    def test_errors_redact_known_credentials_and_terminal_codes(self):
        self.assertEqual(safe_text("\x1b[31mproblem AUTH_TOKEN=abcdef secretvalue\x1b[0m", ["secretvalue"]),
                         "problem AUTH_TOKEN=[REDACTED] [REDACTED]")

    def test_dpapi_alias_priority_forwards_without_printing_or_serializing_key(self):
        self.runner.vault_file = self.root / "vault.json"
        self.runner.vault_file.write_text(json.dumps({"entries": {"test": {"provider": "deepseek", "model": "deepseek-flash", "encrypted_key": "fixture-ciphertext-never-in-command"}}}), encoding="utf-8")
        metadata = self.runner._credential_metadata()
        self.assertEqual(metadata, {"source": "windows_dpapi", "alias": "test", "provider": "deepseek", "model": "deepseek-flash"})
        command = self.runner._credential_command("exec python3 fixed-runner.py")
        self.assertIn("-EncodedCommand", command)
        bridge = base64.b64decode(command[-1]).decode("utf-16-le")
        self.assertIn("ConvertTo-SecureString", bridge)
        self.assertIn("WSLENV", bridge)
        self.assertNotIn("fixture-ciphertext-never-in-command", bridge)
        self.assertNotIn("Write-Output", bridge)
        self.assertIn('if [ -z "${ANTHROPIC_AUTH_TOKEN:-}${ANTHROPIC_API_KEY:-}" ]', self.runner._credential_setup())

    def test_all_failed_sessions_with_observed_http401_finish_failed_and_unknown_cost(self):
        def failed_session(run_id, command, root, stage, timeout):
            capture = root / "capture"
            capture.mkdir()
            (capture / "capture-summary.json").write_text(json.dumps({"actual_cli_sessions": 1,
                "cost_complete": False, "reported_cost_usd": 0,
                "agents": [{"agent_id": "agent_a", "success": False, "timed_out": True, "reported_cost_usd": None}]}), encoding="utf-8")
            with closing(sqlite3.connect(capture / "session.db")) as db, db:
                db.execute("CREATE TABLE llm_calls (status_code INTEGER)")
                db.executemany("INSERT INTO llm_calls VALUES (?)", [(401,), (401,)])
            return {"exit_code": 2, "timed_out": False, "stderr_tail": "", "stdout_tail": ""}
        payload = {"name": "rejected auth", "dataset_id": "error-propagation-v1", "experiment_type": "cross_layer_live", "confirm_api": True}
        with patch.object(self.runner, "preflight", return_value={"ok": True, "checks": []}), patch.object(self.runner, "_run_process", side_effect=failed_session):
            code, response = self.runner.start(payload)
            self.assertEqual(code, 202)
            detail = self.wait(response["id"])
        self.assertEqual(detail["status"], "failed")
        self.assertIn("HTTP 401", detail["error"]["message"])
        self.assertIsNone(detail["api"]["cost_usd"])

    def test_missing_agent_output_keeps_successful_api_and_three_observed_tools(self):
        stages = []
        def successful_capture_missing_write(run_id, command, root, stage, timeout):
            stages.append(stage)
            capture = root / "capture"
            if stage == "capture":
                (capture / "workspace").mkdir(parents=True)
                (capture / "workspace/handoff.json").write_text('{"service":"test","reported_status":"up"}', encoding="utf-8")
                (capture / "capture-summary.json").write_text(json.dumps({"actual_cli_sessions": 2,
                    "cost_complete": True, "reported_cost_usd": 0.055,
                    "agents": [{"agent_id": agent, "success": True, "session_id": agent, "reported_cost_usd": 0.0275} for agent in ("agent_a", "agent_b")]}), encoding="utf-8")
                for agent in ("agent_a", "agent_b"):
                    (capture / (agent + "-launch.json")).write_text("{}", encoding="utf-8")
                with closing(sqlite3.connect(capture / "session.db")) as db, db:
                    db.execute("CREATE TABLE tool_calls (tool_call_id TEXT)")
                    db.executemany("INSERT INTO tool_calls VALUES (?)", [("one",), ("two",), ("three",)])
            if stage == "align":
                (capture / "alignment-inputs").mkdir()
                (capture / "alignment-inputs/real-alignment-comparison.json").write_text(json.dumps({"native_tool_starts": 3, "system_tool_ids": 3, "system_edge_claim_allowed": True,
                    "identity_modes": {"session-and-tool": {"accepted": 3}}}), encoding="utf-8")
            return {"exit_code": 0, "timed_out": False, "stderr_tail": "", "stdout_tail": ""}
        payload = {"name": "missing task write", "dataset_id": "error-propagation-v1", "experiment_type": "cross_layer_live", "confirm_api": True}
        with patch.object(self.runner, "preflight", return_value={"ok": True, "checks": []}), patch.object(self.runner, "_run_process", side_effect=successful_capture_missing_write):
            code, response = self.runner.start(payload)
            self.assertEqual(code, 202)
            detail = self.wait(response["id"])
        self.assertEqual(detail["status"], "partial")
        self.assertEqual(detail["error"]["stage"], "task_output")
        self.assertEqual(detail["api"]["sessions"], 2)
        self.assertEqual(detail["correlation"]["native_tools"], 3)
        self.assertEqual(detail["correlation"]["system_tools"], 3)
        self.assertNotIn("scenario_check", stages)
        self.assertNotIn("Traceback", detail["error"]["message"])
        root = Path(self.repository.get_run(response["id"])["root"])
        status = json.loads((root / "capture/scenario-validation-status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["missing_outputs"], ["workspace/decision.json"])
        self.assertFalse(status["scenario_score_available"])
        self.assertFalse((root / "capture/scenario-score.json").exists())


if __name__ == "__main__":
    unittest.main()
