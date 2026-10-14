import unittest

from verify_native_identity_capture import evaluate


def event(namespace_pid=34, uncertainty=50):
    return {
        "source": "process",
        "pid": 9624,
        "data": {
            "event": "EXEC",
            "pid": 9624,
            "namespace_pid": namespace_pid,
            "full_command": "/bin/echo marker",
            "_agentsight_clock": {
                "raw_boot_ns": 100,
                "boot_epoch_ns": 200,
                "anchor_uncertainty_ns": uncertainty,
                "conversion": "boot_epoch_ns_plus_bpf_ktime_ns",
            },
        },
    }


class NativeIdentityCaptureTests(unittest.TestCase):
    def test_accepts_direct_namespace_mapping_and_nonzero_clock_floor(self):
        result = evaluate([event()], {"marker": "marker", "userspace_pid": 34})
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["evidence"]["pid_mapping_status"], "accepted")
        self.assertEqual(result["evidence"]["observer_anchor_uncertainty_ns"], 50)

    def test_wrong_namespace_pid_abstains(self):
        result = evaluate([event(namespace_pid=35)],
                          {"marker": "marker", "userspace_pid": 34})
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["evidence"]["pid_mapping_status"], "abstain")

    def test_zero_clock_floor_fails(self):
        result = evaluate([event(uncertainty=0)],
                          {"marker": "marker", "userspace_pid": 34})
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["checks"]["clock_resolution_floor_nonzero"])

    def test_duplicate_marker_events_fail(self):
        result = evaluate([event(), event()], {"marker": "marker", "userspace_pid": 34})
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["checks"]["unique_marker_event"])


if __name__ == "__main__":
    unittest.main()
