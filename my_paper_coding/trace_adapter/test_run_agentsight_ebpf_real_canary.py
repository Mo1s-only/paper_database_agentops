import unittest

from run_agentsight_ebpf_real_canary import cumulative_budget_exceeded, preflight_failure_code


class CumulativeBudgetOverrideTests(unittest.TestCase):
    def test_only_explicit_override_skips_cumulative_ceiling(self):
        self.assertTrue(cumulative_budget_exceeded(2.60, 2.59, 2.1, 2.0))
        self.assertFalse(cumulative_budget_exceeded(2.60, 2.59, 2.1, 2.0, True))


class PreflightFailureCodeTests(unittest.TestCase):
    def test_sensitive_failure_details_are_reduced_to_safe_categories(self):
        cases = {
            "Existing credential not loaded": "credential_missing",
            "The one-session upper bound exceeds the existing hard stop": "budget_guard_blocked",
            "Unexpected provider URL; refusing real API call": "provider_guard_blocked",
            "Ubuntu root required for eBPF": "privilege_guard_blocked",
            "unexpected filesystem state": "preflight_failed",
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                self.assertEqual(preflight_failure_code(RuntimeError(message)), expected)


if __name__ == "__main__":
    unittest.main()
