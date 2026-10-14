import copy
import unittest

from application_events_v2 import event
from test_application_events_v2 import anchor, base
from pre_attribution_evidence import build_package, canonical_bytes, verify_package
from test_model_invocation_context import context


def stream():
    shared = base()
    return [
        event(shared, "session.start", 0, anchor(1_000)),
        event(shared, "step.start", 1, anchor(2_000), step_id="step"),
        event(shared, "tool.start", 2, anchor(2_100, True), step_id="step", tool_call_id="tool"),
        event(shared, "tool.end", 3, anchor(3_000), step_id="step", tool_call_id="tool"),
        event(shared, "step.end", 4, anchor(3_100), step_id="step"),
        event(shared, "session.end", 5, anchor(4_000)),
    ]


def gate(identity=True, bounded=False):
    return {"ready_modes": {
        "identity_and_tool_graph": identity,
        "bounded_temporal_ordering": bounded,
        "responsibility_or_root_cause": False,
    }}


class PreAttributionEvidenceTests(unittest.TestCase):
    def test_build_is_deterministic_and_contains_no_attribution(self):
        first = build_package(stream(), gate())
        second = build_package(stream(), gate())
        self.assertEqual(canonical_bytes(first), canonical_bytes(second))
        self.assertEqual(first["claims"], {
            "root_cause_generated": False,
            "responsibility_generated": False,
            "causal_path_generated": False,
        })
        self.assertTrue(verify_package(stream(), first)["passed"])

    def test_closed_identity_gate_refuses_package(self):
        with self.assertRaisesRegex(ValueError, "Identity and tool graph"):
            build_package(stream(), gate(identity=False))

    def test_each_relation_has_replayable_receipt(self):
        package = build_package(stream(), gate())
        query_ids = {query["query_id"] for query in package["queries"]}
        self.assertGreaterEqual(len(package["observed_relations"]), 3)
        for relation in package["observed_relations"]:
            self.assertTrue(relation["evidence_event_ids"])
            self.assertTrue(set(relation["query_ids"]).issubset(query_ids))
            self.assertFalse(relation["causal_claim"])
            self.assertFalse(relation["responsibility_claim"])

    def test_closed_clock_gate_only_allows_sequence_order(self):
        package = build_package(stream(), gate(bounded=False))
        time_relations = {relation["time_relation"] for relation in package["observed_relations"]}
        self.assertNotIn("bounded_application_clock", time_relations)
        self.assertFalse(package["readiness"]["bounded_temporal_relations"])

    def test_watson_mirror_abstains_on_missing_invocation_context(self):
        package = build_package(stream(), gate())
        mirror = package["mirror_readiness"]
        self.assertEqual(mirror["status"], "NOT_READY")
        self.assertFalse(mirror["default_values_invented"])
        self.assertFalse(mirror["reconstruction_attempted"])
        self.assertIn("system_prompt_sha256", mirror["missing_fields"])

    def test_complete_invocation_context_opens_only_reconstruction_readiness(self):
        value = context()
        package = build_package(stream(), gate(), [value])
        self.assertEqual(package["mirror_readiness"]["status"], "READY")
        self.assertTrue(package["readiness"]["reasoning_reconstruction"])
        self.assertFalse(package["readiness"]["causal_attribution"])
        self.assertEqual(package["claims"]["root_cause_generated"], False)

    def test_tampered_query_receipt_is_rejected(self):
        package = build_package(stream(), gate())
        changed = copy.deepcopy(package)
        changed["queries"][0]["result_sha256"] = "0" * 64
        result = verify_package(stream(), changed)
        self.assertFalse(result["passed"])
        self.assertFalse(result["all_queries_replayed"])

    def test_two_sessions_may_reuse_local_step_and_tool_ids(self):
        first = stream()
        second_base = base()
        second_base["session_id"] = "session-2"
        second_base["agent_id"] = "agent-2"
        second_base["process"]["local_pid"] = 11
        second_base["process"]["observer_pid"] = 21
        second = [
            event(second_base, "session.start", 0, anchor(1_100)),
            event(second_base, "step.start", 1, anchor(2_100), step_id="step"),
            event(second_base, "tool.start", 2, anchor(2_200, True), step_id="step", tool_call_id="tool"),
            event(second_base, "tool.end", 3, anchor(3_100), step_id="step", tool_call_id="tool"),
            event(second_base, "step.end", 4, anchor(3_200), step_id="step"),
            event(second_base, "session.end", 5, anchor(4_100)),
        ]
        interleaved = [item for pair in zip(first, second) for item in pair]
        package = build_package(interleaved, gate())
        relation_ids = [item["relation_id"] for item in package["observed_relations"]]
        self.assertEqual(len(relation_ids), 6)
        self.assertEqual(len(set(relation_ids)), 6)
        self.assertTrue(verify_package(interleaved, package)["passed"])


if __name__ == "__main__":
    unittest.main()
