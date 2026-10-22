from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from blind_attribution_eval import predict, score
from run_fault_matrix import FAULTS, build_run


class BlindAttributionTests(unittest.TestCase):
    def test_predictor_has_trace_only_interface(self) -> None:
        self.assertEqual(list(inspect.signature(predict).parameters), ["trace"])

    def test_three_fixture_shapes_without_fault_argument(self) -> None:
        for fault in FAULTS:
            with self.subTest(fault=fault):
                trace, truth = build_run(fault, 1)
                truth["responsible_action_event_id"] = next(
                    event["event_id"] for event in trace
                    if event["step_id"] == truth["responsible_step"]
                )
                prediction = predict(trace)
                result = score(prediction, truth)
                self.assertEqual(prediction["prediction_status"], "single_candidate")
                self.assertTrue(result["agent_exact_match"])
                self.assertTrue(result["step_exact_match"])
                self.assertTrue(result["action_exact_match"])
                self.assertTrue(result["edge_exact_match"])
                self.assertNotIn("fault_type", prediction)
                self.assertNotIn("task_name", prediction)

    def test_ambiguous_candidates_abstain(self) -> None:
        trace, _ = build_run("routing_role_error", 1)
        duplicate = dict(trace[1])
        duplicate.update({"event_id": "evt-extra", "parent_event_id": "evt-001"})
        trace.append(duplicate)
        prediction = predict(trace)
        self.assertEqual(prediction["prediction_status"], "abstain")
        self.assertEqual(prediction["abstain_reason"], "multiple_supported_candidates")

    def test_missing_parent_abstains(self) -> None:
        trace, _ = build_run("error_propagation", 1)
        trace[2]["parent_event_id"] = "absent-parent"
        prediction = predict(trace)
        self.assertEqual(prediction["prediction_status"], "abstain")
        self.assertEqual(prediction["abstain_reason"], "candidate_parent_missing")

    def test_success_without_contract_is_not_called_a_mismatch(self) -> None:
        trace, _ = build_run("silent_tool_error", 1)
        trace[0]["output_summary"] = {"item": "alpha"}
        prediction = predict(trace)
        self.assertEqual(prediction["prediction_status"], "abstain")
        self.assertEqual(prediction["abstain_reason"], "no_supported_candidate")

    def test_irrelevant_fault_label_does_not_change_prediction(self) -> None:
        trace, _ = build_run("routing_role_error", 1)
        baseline = predict(trace)
        with_label = [dict(event, fault_type="misleading_label") for event in trace]
        self.assertEqual(predict(with_label), baseline)


if __name__ == "__main__":
    unittest.main()
