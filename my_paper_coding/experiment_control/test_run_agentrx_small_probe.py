import unittest

from my_paper_coding.experiment_control.run_agentrx_small_probe import (
    build_prompt, check_budget, reported_cost_status,
)


class AgentRxProbeSafetyTest(unittest.TestCase):
    def test_cli_reported_budget_overrun_is_not_treated_as_success(self):
        self.assertEqual(reported_cost_status(0.08, 0.08), "within_cap")
        self.assertEqual(reported_cost_status(0.108088, 0.08), "exceeded_cap")
        self.assertEqual(reported_cost_status(None, 0.08), "unknown")

    def test_prompt_excludes_task_oracle_and_labels(self):
        source = {"task_id": 12, "traj": [{"index": 1, "role": "user", "content": "hello"}],
                  "info": {"secret": "HIDDEN_TASK_ORACLE"},
                  "reward_info": {"secret": "HIDDEN_REWARD"},
                  "root_cause": {"secret": "HIDDEN_ROOT_CAUSE"}}
        prompt = build_prompt(source)
        self.assertIn("hello", prompt)
        for hidden in ("HIDDEN_TASK_ORACLE", "HIDDEN_REWARD", "HIDDEN_ROOT_CAUSE"):
            self.assertNotIn(hidden, prompt)

    def test_combined_cap_uses_actual_first_run_cost(self):
        manifest = {"baseline_ledger_total_usd": 2.183708,
                    "error_propagation_max_usd_per_session": 0.05,
                    "agentrx_max_usd": 0.08, "planning_usd_cny_rate": 10,
                    "batch_cap_cny": 2, "hard_stop_total_usd": 2.363708}
        ledger = {"total_cost_usd": 2.183708}
        error_plan = {"scenario": "error-propagation-v1", "per_session_budget_usd": 0.05}
        error_summary = {"cost_complete": True, "actual_cli_sessions": 2,
                         "reported_cost_usd": 0.07,
                         "agents": [{"success": True}, {"success": True}]}
        budget = check_budget(manifest, ledger, error_summary, error_plan)
        self.assertAlmostEqual(budget["planned_total_cny_at_rate"], 1.5)
        error_summary["reported_cost_usd"] = 0.12
        with self.assertRaises(ValueError):
            check_budget(manifest, ledger, error_summary, error_plan)


if __name__ == "__main__":
    unittest.main()
