import copy
import unittest

from application_events_v2 import canonicalize_events, event
from observation_quality_gate import (
    clock_quality, field_completeness, mapping_coverage, run_negative_matrix,
)
from test_application_events_v2 import anchor, base


def stream():
    shared = base()
    return [
        event(shared, "session.start", 0, anchor(1_000)),
        event(shared, "step.start", 1, anchor(2_000), step_id="step"),
        event(shared, "tool.start", 2, anchor(2_000, True),
              step_id="step", tool_call_id="tool"),
        event(shared, "tool.end", 3, anchor(3_000),
              step_id="step", tool_call_id="tool"),
        event(shared, "step.end", 4, anchor(3_000), step_id="step"),
        event(shared, "session.end", 5, anchor(4_000)),
    ]


class ObservationQualityGateTests(unittest.TestCase):
    def test_canonical_replay_ignores_random_source_event_ids(self):
        first = stream()
        second = copy.deepcopy(first)
        for index, value in enumerate(second):
            value["event_id"] = f"random-{index}"
        self.assertEqual(canonicalize_events(first), canonicalize_events(second))

    def test_mapping_coverage_counts_sessions_not_repeated_events(self):
        result = mapping_coverage(stream())
        self.assertEqual(result["session_total"], 1)
        self.assertEqual(result["session_counts"]["inferred"], 1)
        self.assertEqual(result["event_counts"]["inferred"], 6)

    def test_zero_uncertainty_is_reported_as_quality_failure(self):
        result = clock_quality(stream())
        self.assertEqual(result["zero_uncertainty_event_count"], 0)
        values = stream()
        values[2]["clock"]["observer_anchor_uncertainty_ns"] = 0
        result = clock_quality(values)
        self.assertEqual(result["zero_uncertainty_event_count"], 1)
        self.assertFalse(result["resolution_floor_gate_passed"])

    def test_negative_protocol_matrix_rejects_every_case(self):
        result = run_negative_matrix(stream())
        self.assertEqual(result["case_count"], 8)
        self.assertTrue(result["all_invalid_cases_rejected"])

    def test_required_field_completeness_is_explicit(self):
        result = field_completeness(stream())
        self.assertEqual(result["overall_rate"], 1.0)
        self.assertTrue(result["all_required_lifecycle_kinds_present"])
        self.assertEqual(result["groups"]["tool_start_observer_clock"]["rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
