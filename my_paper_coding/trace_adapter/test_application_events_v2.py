import copy
import unittest

from application_events_v2 import VERSION, event, validate_event, validate_stream


def anchor(realtime, observer=False):
    value = {
        "application_realtime_ns": realtime,
        "application_realtime_interval_ns": [realtime - 2, realtime + 2],
        "application_monotonic_ns": realtime - 100,
        "application_boottime_ns": realtime - 90,
        "application_uncertainty_ns": 2,
        "observer_raw_boot_ns": None,
        "observer_epoch_ms": None,
        "observer_boot_epoch_ns": None,
        "observer_anchor_uncertainty_ns": None,
        "conversion": None,
        "correction_ns": None,
    }
    if observer:
        value.update({
            "observer_raw_boot_ns": 600_000_000,
            "observer_epoch_ms": 2_100,
            "observer_boot_epoch_ns": 1_500_000_000,
            "observer_anchor_uncertainty_ns": 10,
            "conversion": "boot_epoch_ns_plus_bpf_ktime_ns",
            "correction_ns": 0,
        })
    return value


def base():
    return {
        "schema_version": VERSION,
        "evidence_kind": "synthetic_fixture",
        "run_id": "run",
        "session_id": "session",
        "agent_id": "agent",
        "process": {
            "host_id": "host", "boot_id": "boot",
            "local_pid": 10, "local_pid_namespace": "pid:[1]",
            "observer_pid": 20,
            "observer_pid_namespace": "linux-initial-pid-namespace",
            "mapping_status": "inferred",
            "mapping_method": "fixture",
            "mapping_evidence": ["fixture-evidence"],
            "start_realtime_interval_ns": [1, 5],
            "observer_start_epoch_ms": 2,
        },
    }


class ApplicationEventV2Tests(unittest.TestCase):
    def test_complete_stream_with_dual_pid_and_raw_clock(self):
        shared = base()
        events = [
            event(shared, "session.start", 0, anchor(1_000)),
            event(shared, "step.start", 1, anchor(2_000), step_id="step"),
            event(shared, "tool.start", 2, anchor(2_000, True),
                  step_id="step", tool_call_id="tool"),
            event(shared, "tool.end", 3, anchor(3_000),
                  step_id="step", tool_call_id="tool"),
            event(shared, "step.end", 4, anchor(3_000), step_id="step"),
            event(shared, "session.end", 5, anchor(4_000)),
        ]
        result = validate_stream(events)
        self.assertTrue(result["all_sessions_closed"])
        self.assertEqual(result["event_count"], 6)

    def test_rejects_inconsistent_observer_formula(self):
        value = event(base(), "session.start", 0, anchor(1_000))
        value["clock"] = anchor(1_000, True)
        value["clock"]["observer_epoch_ms"] = 2_099
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_event(value)

    def test_rejects_changed_process_mapping(self):
        shared = base()
        first = event(shared, "session.start", 0, anchor(1_000))
        changed = copy.deepcopy(shared)
        changed["process"]["observer_pid"] = 21
        second = event(changed, "session.end", 1, anchor(2_000))
        with self.assertRaisesRegex(ValueError, "changed process"):
            validate_stream([first, second])

    def test_accepted_mapping_requires_direct_nspid_evidence(self):
        shared = base()
        shared["process"].update(
            mapping_status="accepted",
            mapping_method="proc_status_nspid",
            mapping_evidence=["proc.status.NSpid=100,1"],
        )
        validate_event(event(shared, "session.start", 0, anchor(1_000)))
        shared["process"]["mapping_method"] = "fixture"
        with self.assertRaisesRegex(ValueError, "direct NSpid"):
            event(shared, "session.start", 0, anchor(1_000))

    def test_abstain_cannot_claim_observer_pid(self):
        shared = base()
        shared["process"].update(
            mapping_status="abstain", mapping_method=None,
            mapping_evidence=["ambiguous_local_pid"], observer_pid=None,
            observer_pid_namespace=None, observer_start_epoch_ms=None,
        )
        validate_event(event(shared, "session.start", 0, anchor(1_000)))
        shared["process"]["observer_pid"] = 20
        with self.assertRaisesRegex(ValueError, "cannot claim"):
            event(shared, "session.start", 0, anchor(1_000))

    def test_every_mapping_decision_requires_unique_evidence(self):
        shared = base()
        shared["process"]["mapping_evidence"] = []
        with self.assertRaisesRegex(ValueError, "unique evidence"):
            event(shared, "session.start", 0, anchor(1_000))
        shared["process"]["mapping_evidence"] = ["same", "same"]
        with self.assertRaisesRegex(ValueError, "unique evidence"):
            event(shared, "session.start", 0, anchor(1_000))


if __name__ == "__main__":
    unittest.main()
