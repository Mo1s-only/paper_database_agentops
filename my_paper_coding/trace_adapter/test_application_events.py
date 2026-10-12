import copy
import json
from pathlib import Path
import tempfile
import unittest

from application_events import EventWriter, read_events, validate_stream
from align_application import join_application
from run_application_gate import fixture_events, fixture_records, fixture_scope, scenarios


class ApplicationTests(unittest.TestCase):
    def test_adversarial_protocol_matrix(self):
        for case in scenarios(fixture_events(), fixture_records(), fixture_scope()):
            with self.subTest(case=case["name"]):
                self.assertTrue(case["passed"], case)

    def test_exact_expected_identities(self):
        decisions, summary = join_application(fixture_events(), fixture_records(), fixture_scope(), "app.jsonl")
        self.assertEqual([(d["agent_id"], d["step_id"], d["target_ref"]) for d in decisions],
                         [("agent_a", "step-a", "fixture.db#tool_calls/tool-a"),
                          ("agent_b", "step-b", "fixture.db#tool_calls/tool-b")])
        self.assertTrue(summary["tool_identity_gate_passed"])
        self.assertFalse(summary["unified_trace_ready"])

    def test_matrix_does_not_depend_on_sqlite_table_order(self):
        records = sorted(fixture_records(), key=lambda r: r["record_type"])
        for case in scenarios(fixture_events(), records, fixture_scope()):
            with self.subTest(case=case["name"]):
                self.assertTrue(case["passed"], case)

    def test_derived_and_validator_cannot_supply_shared_id(self):
        for role in ("derived", "validator"):
            records = fixture_records()
            records[1]["source"]["role"] = role
            decisions, _ = join_application(fixture_events(), records, fixture_scope(), "app.jsonl")
            self.assertEqual(decisions[0]["status"], "abstain")

    def test_other_source_does_not_supply_identity(self):
        scope = fixture_scope("other.db")
        decisions, _ = join_application(fixture_events(), fixture_records(), scope, "app.jsonl")
        self.assertTrue(all(d["status"] == "abstain" for d in decisions))

    def test_undeclared_label_field_rejected(self):
        events = fixture_events()
        events[0]["responsible_agent"] = "agent_b"
        with self.assertRaises(ValueError):
            validate_stream(events)

    def test_event_id_duplicate_rejected(self):
        events = fixture_events()
        events[1]["event_id"] = events[0]["event_id"]
        with self.assertRaises(ValueError):
            validate_stream(events)

    def test_tool_id_reuse_rejected(self):
        events = fixture_events()
        events[3]["event_type"] = "tool.start"
        with self.assertRaisesRegex(ValueError, "Tool ID reused"):
            validate_stream(events)

    def test_open_step_cannot_end_session(self):
        events = fixture_events()
        events[4].update(event_type="session.end", step_id=None)
        with self.assertRaises(ValueError):
            validate_stream(events)

    def test_backwards_time_rejected(self):
        events = fixture_events()
        events[3]["timestamp_ms"] = 1101
        with self.assertRaises(ValueError):
            validate_stream(events)

    def test_closed_session_cannot_restart(self):
        events = fixture_events()[:6]
        extra = copy.deepcopy(events[0]); extra.update(event_id="restart", sequence=6, timestamp_ms=1200)
        with self.assertRaises(ValueError):
            validate_stream(events + [extra])

    def test_writer_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            events = fixture_events()[:6]; head = events[0]
            writer = EventWriter(path, head["run_id"], head["session_id"], head["agent_id"], head["process"], head["clock"], "synthetic_fixture")
            try:
                for e in events:
                    writer.emit(e["event_type"], e["step_id"], e["tool_call_id"], e["timestamp_ms"])
                self.assertTrue(writer.finish()["all_sessions_closed"])
            finally:
                writer.close()
            parsed, info = read_events(path)
            self.assertEqual(len(parsed), 6)
            with self.assertRaises(FileExistsError):
                EventWriter(path, head["run_id"], head["session_id"], head["agent_id"], head["process"], head["clock"])

    def test_partial_log_is_preserved_but_not_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "partial.jsonl"; head = fixture_events()[0]
            writer = EventWriter(path, head["run_id"], head["session_id"], head["agent_id"], head["process"], head["clock"], "synthetic_fixture")
            writer.emit("session.start", timestamp_ms=head["timestamp_ms"])
            with self.assertRaises(ValueError):
                writer.finish()
            self.assertTrue(path.exists())
            with self.assertRaises(ValueError):
                read_events(path)

    def test_legacy_result_is_not_a_complete_event(self):
        with self.assertRaises(ValueError):
            validate_stream([{"session_id": "old", "result": "success"}])


if __name__ == "__main__":
    unittest.main()
