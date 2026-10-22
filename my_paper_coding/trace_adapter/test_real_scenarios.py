import json
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from capture_real_scenarios import (append_lifecycle, budget_projection,
                                    cumulative_budget_preflight,
                                    diagnose_capture_coverage,
                                    agentsight_binary_identity)
from run_agentsight_ebpf_real_canary import (DEEPSEEK_ANTHROPIC_BASE_URL,
                                             configure_deepseek_environment,
                                             preflight as canary_preflight)
from validate_real_scenarios import capture_gate, decode_result, native_tools, score
from claude_tool_id_bridge_hook import process_hook


class RealScenarioValidationTests(unittest.TestCase):
    def test_tool_id_bridge_hook_wraps_controlled_bash_and_logs_post_event(self):
        with tempfile.TemporaryDirectory() as temp:
            events = Path(temp) / "events.jsonl"
            payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                       "tool_use_id": "call_test_123",
                       "tool_input": {"command": 'python3 "scenario_service_observer.py"'}}
            payload["tool_input"]["command"] = 'python3 "scenario_service_observer.py"'
            result = process_hook(payload, events, allow_known_scenario_scripts=True)
            wrapped = result["hookSpecificOutput"]["updatedInput"]["command"]
            self.assertIn("AGENTOPS_TOOL_CALL_ID=call_test_123", wrapped)
            self.assertIn("scenario_service_observer.py", wrapped)
            post = {"hook_event_name": "PostToolUse", "tool_name": "Bash",
                    "tool_use_id": "call_test_123"}
            self.assertIsNone(process_hook(post, events, allow_known_scenario_scripts=True))
            rows = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([row["hook_event_name"] for row in rows], ["PreToolUse", "PostToolUse"])
        self.assertNotIn("command", rows[0])

    def test_tool_id_bridge_does_not_rewrite_arbitrary_bash(self):
        with tempfile.TemporaryDirectory() as temp:
            events = Path(temp) / "events.jsonl"
            payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                       "tool_use_id": "call_test_456",
                       "tool_input": {"command": "cd /tmp && ./user-script.sh"}}
            result = process_hook(payload, events, allow_known_scenario_scripts=True)
            rows = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
        self.assertIsNone(result)
        self.assertFalse(rows[0]["command_tagged"])

    def test_tool_id_bridge_ignores_non_bash_tools(self):
        with tempfile.TemporaryDirectory() as temp:
            events = Path(temp) / "events.jsonl"
            payload = {"hook_event_name": "PreToolUse", "tool_name": "Read",
                       "tool_use_id": "call_read_123",
                       "tool_input": {"file_path": "/tmp/input.txt"}}
            result = process_hook(payload, events, allow_known_scenario_scripts=True)
        self.assertIsNone(result)
        self.assertFalse(events.exists())

    def test_concurrent_hook_processes_append_complete_distinct_events(self):
        with tempfile.TemporaryDirectory() as temp:
            events = Path(temp) / "events.jsonl"
            hook = Path(__file__).with_name("claude_tool_id_bridge_hook.py")
            payloads = [{
                "hook_event_name": "PreToolUse", "tool_name": "Bash",
                "tool_use_id": f"call_parallel_{index}",
                "tool_input": {"command": f'python3 "/tmp/scenario_service_observer.py" --case {index}'},
            } for index in range(16)]

            def invoke(payload):
                result = subprocess.run(
                    [sys.executable, str(hook), "--events", str(events),
                     "--allow-known-scenario-scripts"],
                    input=json.dumps(payload), capture_output=True, text=True, check=False)
                if result.returncode:
                    raise AssertionError(f"hook subprocess failed: {result.stderr}")
                return result

            with ThreadPoolExecutor(max_workers=16) as pool:
                results = list(pool.map(invoke, payloads))
            rows = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
            self.assertFalse(events.with_name(events.name + ".lock").exists())
        self.assertEqual(len(rows), len(payloads))
        self.assertEqual({row["tool_call_id"] for row in rows},
                         {payload["tool_use_id"] for payload in payloads})
        returned = [json.loads(result.stdout)["hookSpecificOutput"]["updatedInput"]["command"]
                    for result in results]
        for payload, command in zip(payloads, returned):
            self.assertIn(payload["tool_use_id"], command)

    def test_agentsight_binary_identity_is_pinned_before_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            binary = Path(temp) / "agentsight"
            binary.write_bytes(b"fixture-agent-sight-binary")
            import hashlib
            expected = hashlib.sha256(binary.read_bytes()).hexdigest()
            identity = agentsight_binary_identity(binary, expected)
            self.assertEqual(identity["sha256"], expected)
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                agentsight_binary_identity(binary, "0" * 64)

    def test_deepseek_key_alias_is_process_local_and_sets_compatible_endpoint(self):
        environment = {"DEEPSEEK_API_KEY": "fixture-secret"}
        self.assertTrue(configure_deepseek_environment(environment))
        self.assertEqual(environment["ANTHROPIC_AUTH_TOKEN"], "fixture-secret")
        self.assertEqual(environment["ANTHROPIC_BASE_URL"], DEEPSEEK_ANTHROPIC_BASE_URL)

    def test_existing_claude_credentials_and_endpoint_are_preserved(self):
        environment = {
            "ANTHROPIC_API_KEY": "existing-fixture",
            "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
            "DEEPSEEK_API_KEY": "unused-fixture",
        }
        self.assertTrue(configure_deepseek_environment(environment))
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", environment)
        self.assertEqual(environment["ANTHROPIC_API_KEY"], "existing-fixture")
        self.assertEqual(environment["ANTHROPIC_BASE_URL"], "https://api.deepseek.com/anthropic")

    def test_preflight_accounts_for_known_prior_session_overage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output_parent = root / "runs"
            output_parent.mkdir()
            output = output_parent / "real-canary-next"
            previous_run = output_parent / "real-canary-prior"
            previous_run.mkdir()
            (previous_run / "diagnostic-summary.json").write_text(json.dumps({
                "real_api": True,
                "cost_status": "exceeded_session_limit",
                "cli": {"reported_cost_usd": 0.0237776},
            }), encoding="utf-8")
            ledger = root / "ledger.json"
            ledger.write_text(json.dumps({"total_cost_usd": 1.0}), encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "baseline_ledger_total_usd": 1.0,
                "historical_ledger_override": {"approved_by_user": True},
                "hard_stop_total_usd": 2.0,
                "planning_usd_cny_rate": 10.0,
            }), encoding="utf-8")
            scenario = root / "scenario.json"
            scenario.write_text(json.dumps({
                "cost_complete": True, "actual_cli_sessions": 2,
                "reported_cost_usd": 0.05,
            }), encoding="utf-8")
            agentrx = root / "agentrx.json"
            agentrx.write_text(json.dumps({"is_error": False, "total_cost_usd": 0.05}), encoding="utf-8")
            patches = (
                mock.patch("run_agentsight_ebpf_real_canary.BASELINE", ledger),
                mock.patch("run_agentsight_ebpf_real_canary.MANIFEST", manifest),
                mock.patch("run_agentsight_ebpf_real_canary.PREVIOUS_SCENARIO", scenario),
                mock.patch("run_agentsight_ebpf_real_canary.PREVIOUS_AGENTRX", agentrx),
                mock.patch("run_agentsight_ebpf_real_canary.os.geteuid", return_value=0, create=True),
                mock.patch("run_agentsight_ebpf_real_canary.Path.exists", return_value=True),
            )
            for patcher in patches:
                patcher.start()
            try:
                with mock.patch.dict(os.environ, {
                    "ANTHROPIC_AUTH_TOKEN": "fixture-only",
                    "ANTHROPIC_BASE_URL": DEEPSEEK_ANTHROPIC_BASE_URL,
                }, clear=True):
                    budget = canary_preflight(output, 0.02)
            finally:
                for patcher in reversed(patches):
                    patcher.stop()
        self.assertEqual(budget["previous_canaries"][0]["cost_status"], "exceeded_session_limit")
        self.assertAlmostEqual(budget["previous_canary_usd"], 0.0237776)
        self.assertLess(budget["projected_incremental_cny_at_planning_rate"], 2.0)

    def test_coverage_diagnosis_separates_network_and_semantic_layers(self):
        result = diagnose_capture_coverage(
            {"llm_calls": 0, "tool_calls": 0},
            [{"pid": 1283, "comm": "HTTP Client", "host": "api.deepseek.com",
              "path": "/anthropic/v1/messages?beta=true", "count": 3}],
            {1283},
        )
        self.assertEqual(result["status"], "endpoint_seen_but_llm_rows_missing")
        self.assertEqual(result["first_unverified_stage"], "network_to_llm_semantics")
        self.assertTrue(result["endpoint_pid_matches_claude_process"])
        self.assertEqual(result["matched_claude_pids"], [1283])
        self.assertIn("not proof", result["interpretation"])

    def test_coverage_diagnosis_points_to_tool_response_when_llm_rows_exist(self):
        result = diagnose_capture_coverage(
            {"llm_calls": 2, "tool_calls": 0},
            [{"pid": 1283, "path": "/v1/messages"}],
            {1283},
        )
        self.assertEqual(result["status"], "llm_rows_seen_but_tool_rows_missing")
        self.assertEqual(result["first_unverified_stage"], "llm_response_to_tool_semantics")

    def test_lifecycle_records_health_without_environment_secrets(self):
        class Process:
            pid = 123

            def poll(self):
                return None

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "lifecycle.jsonl"
            row = append_lifecycle(path, "capture_ready", Process(), Process(), agent="agent_a")
            saved = json.loads(path.read_text(encoding="utf-8").strip())
        self.assertEqual(saved["stage"], "capture_ready")
        self.assertEqual(saved["observer_pid"], 123)
        self.assertIsNone(saved["observer_exit_code"])
        self.assertEqual(saved["agent"], "agent_a")
        self.assertNotIn("api_key", saved)
        self.assertIn("monotonic_ns", row)

    def test_two_session_budget_stays_under_two_cny_with_margin(self):
        budget = budget_projection(0.12, 2, 8.0, 2.0)
        self.assertEqual(budget["projected_usd"], 0.24)
        self.assertEqual(budget["projected_cny"], 1.92)
        self.assertTrue(budget["within_cap"])

    def test_budget_projection_blocks_over_cap(self):
        budget = budget_projection(0.13, 2, 8.0, 2.0)
        self.assertFalse(budget["within_cap"])

    def test_cumulative_budget_preflight_blocks_existing_hard_stop(self):
        result = cumulative_budget_preflight(
            {"hard_stop_total_usd": 2.0}, {"total_cost_usd": 2.183708}, 0.24)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["projected_total_usd"], 2.423708)
        self.assertEqual(result["network_calls_made"], 0)

    def test_cumulative_budget_preflight_allows_within_hard_stop(self):
        result = cumulative_budget_preflight(
            {"hard_stop_total_usd": 2.0}, {"total_cost_usd": 1.5}, 0.24)
        self.assertEqual(result["status"], "PASS")

    def test_decode_native_json_result(self):
        self.assertEqual(decode_result('{"consistent": false}'), {"consistent": False})
        self.assertIsNone(decode_result("plain output"))

    def test_semantic_step_ids_are_per_agent_and_tool_name(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            for suffix, agent in (("a", "agent_a"), ("b", "agent_b")):
                rows = [
                    {"message": {"content": [{"type": "tool_use", "id": f"{suffix}-1", "name": "Bash"}]}},
                    {"message": {"content": [{"type": "tool_result", "tool_use_id": f"{suffix}-1",
                                                "content": '{"ok": true}'}]}},
                    {"message": {"content": [{"type": "tool_use", "id": f"{suffix}-2", "name": "Write"}]}},
                    {"message": {"content": [{"type": "tool_result", "tool_use_id": f"{suffix}-2",
                                                "content": '{"written": true}'}]}},
                ]
                (run / f"claude-agent-{suffix}.log").write_text(
                    "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            self.assertEqual([tool["semantic_step_id"] for tool in native_tools(run)],
                             ["agent_a.bash_1", "agent_a.write_1", "agent_b.bash_1", "agent_b.write_1"])

    def test_exact_score_covers_agent_step_and_edges(self):
        values = {"fault_type": "error_propagation", "responsible_agent": "agent_a",
                  "responsible_step": "agent_a.bash_1",
                  "responsible_edge": {"from": "agent_a.bash_1", "to": "agent_a.write_1"},
                  "propagation_edge": {"from": "agent_a.write_1", "to": "agent_b.bash_1"}}
        prediction = {**values, "task_outcome": {"failed": True}}
        result = score(prediction, values)
        self.assertTrue(result["all_attribution_fields_exact"])
        self.assertTrue(result["task_failure_observed"])

    def test_step_mismatch_prevents_all_exact(self):
        prediction = {"fault_type": "routing_role_error", "responsible_agent": "agent_a",
                      "responsible_step": "agent_a.write_1", "responsible_edge": {},
                      "propagation_edge": {}, "task_outcome": {"failed": True}}
        truth = {**prediction, "responsible_step": "agent_a.bash_1"}
        result = score(prediction, truth)
        self.assertFalse(result["responsible_step_exact"])
        self.assertFalse(result["all_attribution_fields_exact"])

    def test_capture_gate_blocks_partial_system_edge_claim(self):
        alignment = {"native_tool_starts": 4, "system_tool_ids": 3, "missing_ids": [{"tool_call_id": "x"}],
                     "identity_modes": {"session-and-tool": {"accepted": 3, "abstain": 1}}}
        self.assertEqual(capture_gate(alignment)["capture_status"], "incomplete")
        self.assertFalse(capture_gate(alignment)["system_edge_claim_allowed"])

    def test_capture_gate_accepts_one_to_one_coverage(self):
        alignment = {"native_tool_starts": 3, "system_tool_ids": 3, "missing_ids": [],
                     "identity_modes": {"session-and-tool": {"accepted": 3}}}
        self.assertTrue(capture_gate(alignment)["system_edge_claim_allowed"])


if __name__ == "__main__":
    unittest.main()
