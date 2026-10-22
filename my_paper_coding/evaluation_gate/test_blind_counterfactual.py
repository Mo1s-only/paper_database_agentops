from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PILOT_DIR = HERE.parent / "failure_pilot"
sys.path.insert(0, str(PILOT_DIR))
sys.path.insert(0, str(HERE))

from blind_attribution_eval import predict, score
from blind_counterfactual import validate_counterfactual
from prepare_blind_counterfactual_fixtures import TASKS, build


class BlindCounterfactualTests(unittest.TestCase):
    def test_prediction_and_generic_repair_control_across_task_shapes(self) -> None:
        for task in TASKS:
            with self.subTest(task=task):
                trace, truth, plan = build(task, 1)
                prediction = predict(trace)
                prediction["run_id"] = trace[0]["run_id"]
                scored = score(prediction, truth)
                cf = validate_counterfactual(trace, prediction, plan)
                self.assertTrue(scored["action_exact_match"])
                self.assertEqual(cf["status"], "evaluated")
                self.assertTrue(cf["repaired_success"])
                self.assertFalse(cf["control_success"])
                self.assertTrue(cf["counterfactual_flip"])

    def test_counterfactual_does_not_use_prediction_if_candidate_disagrees(self) -> None:
        trace, _, plan = build("inventory", 1)
        prediction = predict(trace)
        prediction["run_id"] = trace[0]["run_id"]
        plan["repair"]["event_id"] = "not-the-predicted-candidate"
        result = validate_counterfactual(trace, prediction, plan)
        self.assertEqual(result["status"], "not_tested")
        self.assertEqual(result["reason"], "prediction_does_not_select_planned_repair_target")

    def test_counterfactual_rejects_cross_run_plan(self) -> None:
        trace, _, plan = build("inventory", 1)
        prediction = predict(trace)
        prediction["run_id"] = trace[0]["run_id"]
        prediction["run_id"] = "another-run"
        result = validate_counterfactual(trace, prediction, plan)
        self.assertEqual(result["status"], "not_tested")
        self.assertEqual(result["reason"], "prediction_trace_run_id_mismatch")


if __name__ == "__main__":
    unittest.main()
