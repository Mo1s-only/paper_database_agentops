import json
from pathlib import Path
import tempfile
import unittest

from validate_real_scenarios import capture_gate, decode_result, native_tools, score


class RealScenarioValidationTests(unittest.TestCase):
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
