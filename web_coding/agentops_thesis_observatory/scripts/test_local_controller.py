"""Focused safety and offline execution checks for the loopback controller."""
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

import local_controller as module


class LocalControllerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.run_dir_patch = patch.object(module, "RUN_DIR", Path(self.temporary.name))
        self.run_dir_patch.start()
        self.addCleanup(self.run_dir_patch.stop)
        self.controller = module.ExperimentController()

    def test_paid_batch_cannot_start_with_missing_ubuntu(self):
        with patch.object(module, "command_probe", return_value=(False, "1")):
            check = self.controller.preflight("error-propagation-v1")
            code, response = self.controller.start("real batch", "error-propagation-v1", True)
        self.assertFalse(check["can_start"])
        self.assertEqual(code, 409)
        self.assertIn("preflight", response)
        self.assertEqual(self.controller.list_runs(), [])

    def test_frozen_ledger_override_is_exact_and_scoped(self):
        manifest = module.read_json(module.MANIFEST)
        ledger = module.read_json(module.LEDGER)
        self.assertTrue(module.frozen_ledger_override_allowed(manifest, ledger))
        altered = {**manifest, "batch_id": "another-batch"}
        self.assertFalse(module.frozen_ledger_override_allowed(altered, ledger))
        altered = {**manifest, "historical_ledger_override": {}}
        self.assertFalse(module.frozen_ledger_override_allowed(altered, ledger))
        altered_ledger = {**ledger, "total_cost_usd": ledger["total_cost_usd"] + 0.01}
        self.assertFalse(module.frozen_ledger_override_allowed(manifest, altered_ledger))

    def test_agentrx_continuation_is_one_time_and_requires_complete_prior_cost(self):
        run_id = "run-123456789abc"
        folder = module.RUN_DIR / run_id
        preceding = folder / "error-propagation"
        preceding.mkdir(parents=True)
        module.write_json(folder / "state.json", {
            "run_id": run_id, "kind": "authorized_live_batch", "status": "FAILED",
            "stage": "FINISHED", "result": {"failed_stage": "error_propagation", "api_calls": 2},
            "events": [], "finished_at": module.now()})
        module.write_json(preceding / "capture-summary.json", {
            "reported_cost_usd": 0.0540648, "cost_complete": True,
            "cost_cap_status": "within_cap", "actual_cli_sessions": 2,
            "agents": [{"success": True}, {"success": True}]})
        module.write_json(preceding / "plan.json", {
            "scenario": "error-propagation-v1", "per_session_budget_usd": 0.05})
        code, _ = self.controller.continue_agentrx(run_id, False)
        self.assertEqual(code, 409)
        with patch.object(module.threading, "Thread") as thread:
            code, response = self.controller.continue_agentrx(run_id, True)
            self.assertEqual(code, 202, response)
            thread.return_value.start.assert_called_once()
        self.assertEqual(self.controller.state(run_id)["stage"], "AGENTRX_QUEUED")
        code, _ = self.controller.continue_agentrx(run_id, True)
        self.assertEqual(code, 409)

    def test_unapproved_paid_dataset_is_rejected(self):
        check = self.controller.preflight("routing-error-v1")
        self.assertFalse(check["can_start"])
        self.assertEqual(check["kind"], "not_authorized")

    def test_public_and_synthetic_inputs_are_audited_without_api(self):
        for dataset_id in ("who-when", "trail", "agenttrace", "alignment-stress-1000"):
            with self.subTest(dataset_id=dataset_id):
                check = self.controller.preflight(dataset_id)
                self.assertTrue(check["can_start"])
                code, response = self.controller.start("offline " + dataset_id, dataset_id, False)
                self.assertEqual(code, 201)
                run_id = response["run_id"]
                for _ in range(100):
                    state = self.controller.state(run_id)
                    if state["status"] != "RUNNING":
                        break
                    time.sleep(0.05)
                self.assertEqual(state["status"], "COMPLETED", state)
                self.assertEqual(state["result"]["api_calls"], 0)
                self.assertEqual(state["result"]["parsed_records"], state["result"]["expected_records"])


if __name__ == "__main__":
    unittest.main()
