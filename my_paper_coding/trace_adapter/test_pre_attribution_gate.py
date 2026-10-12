import copy
import unittest

from pre_attribution_gate import evaluate


def inputs():
    quality = {
        "stream": {"all_sessions_closed": True},
        "field_completeness": {"all_required_lifecycle_kinds_present": True,
                               "overall_rate": 1.0},
        "deterministic_replay": {"byte_identical": True},
        "negative_protocol_matrix": {"all_invalid_cases_rejected": True},
        "mapping_coverage": {"session_counts": {"accepted": 0, "inferred": 1,
                                                  "abstain": 0}},
        "clock_quality": {"resolution_floor_gate_passed": False},
    }
    analysis = {
        "framework_lifecycle": {"tool_use": 1},
        "agentsight_tool_match_count": 1,
        "native_tool_closed": True,
        "agentsight_tool_epoch_formula_verified": True,
        "applied_clock_correction_ns": 0,
    }
    matrix = {"acceptance_passed": True}
    return quality, analysis, matrix


class PreAttributionGateTests(unittest.TestCase):
    def test_identity_graph_ready_but_legacy_clock_warns(self):
        result = evaluate(*inputs())
        self.assertEqual(result["status"], "READY_WITH_WARNINGS")
        self.assertTrue(result["ready_modes"]["identity_and_tool_graph"])
        self.assertFalse(result["ready_modes"]["bounded_temporal_ordering"])

    def test_capture_gap_blocks_identity_graph(self):
        quality, analysis, matrix = inputs()
        analysis["agentsight_tool_match_count"] = 0
        result = evaluate(quality, analysis, matrix)
        self.assertEqual(result["status"], "NOT_READY")
        self.assertFalse(result["checks"]["native_tool_capture_complete"])

    def test_nonzero_clock_floor_promotes_full_observation_gate(self):
        quality, analysis, matrix = inputs()
        quality["clock_quality"]["resolution_floor_gate_passed"] = True
        quality["mapping_coverage"]["session_counts"] = {
            "accepted": 1, "inferred": 0, "abstain": 0}
        result = evaluate(quality, analysis, matrix)
        self.assertEqual(result["status"], "READY")
        self.assertTrue(result["ready_modes"]["bounded_temporal_ordering"])


if __name__ == "__main__":
    unittest.main()
