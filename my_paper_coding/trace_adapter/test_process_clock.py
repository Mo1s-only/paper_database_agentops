import unittest

from analyze_framework_process_clock import (
    boot_second_correction_ns, choose_clock_conversion, choose_native_pid_mapping, inside,
)


class ProcessClockTests(unittest.TestCase):
    def test_boot_second_correction_preserves_fractional_second(self):
        self.assertEqual(boot_second_correction_ns(1_791_615_119_413_555_968), 413_555_968)

    def test_corrected_start_requires_launch_interval(self):
        self.assertTrue(inside(130.556, [129.423, 130.928]))
        self.assertFalse(inside(128.0, [129.423, 130.928]))

    def test_native_high_precision_does_not_apply_legacy_correction(self):
        result = choose_clock_conversion(130.556, [129.423, 130.928], 413_555_968)
        self.assertEqual(result["mode"], "nanosecond_boot_epoch")
        self.assertEqual(result["applied_correction_ns"], 0)

    def test_legacy_integer_second_is_repaired(self):
        result = choose_clock_conversion(129_000.0, [129_400.0, 130_000.0], 500_000_000)
        self.assertEqual(result["mode"], "legacy_integer_second_boot_epoch")
        self.assertEqual(result["resolved_start_ms"], 129_500.0)

    def test_unique_bpf_namespace_pid_mapping_is_accepted(self):
        rows = [{
            "pid": 1791, "action": "exec",
            "details_json": '{"event":"EXEC","namespace_pid":34}',
        }]
        result = choose_native_pid_mapping(rows, 34, [1791])
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["evidence"], ["bpf.pidns.tgid=1791,34"])

    def test_ambiguous_bpf_mapping_does_not_claim_acceptance(self):
        rows = [
            {"pid": pid, "action": "exec",
             "details_json": '{"event":"EXEC","namespace_pid":34}'}
            for pid in (1791, 1792)
        ]
        result = choose_native_pid_mapping(rows, 34, [1791, 1792])
        self.assertEqual(result["status"], "inferred")
        self.assertIsNone(result["observer_pid"])


if __name__ == "__main__":
    unittest.main()
