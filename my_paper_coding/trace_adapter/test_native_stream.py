import copy
import json
from pathlib import Path
import tempfile
import unittest

from align_application import join_application
from parse_claude_native import convert_agent
from run_application_gate import fixture_events, fixture_records, fixture_scope


class SharedIdentifierTests(unittest.TestCase):
    def session_records(self):
        records = fixture_records()
        for label, proc in (("a", 101), ("b", 202)):
            records.append({"record_type": "agentsight.llm_calls", "evidence_status": "observed",
                "timestamp": 1100, "pid": proc, "fields": {"session_id": f"session-{label}", "pid": proc},
                "source": {"path": "fixture.db", "table": "llm_calls", "row": f"llm-{label}", "role": "raw_observation"}})
        return records

    def test_session_and_tool_mode_binds_agent_to_system_pid(self):
        decisions, report = join_application(fixture_events(), self.session_records(), fixture_scope(), "app", "session-and-tool")
        self.assertEqual([d["status"] for d in decisions], ["accepted", "accepted"])
        self.assertEqual([d["session_system_pid"] for d in decisions], [101, 202])
        self.assertEqual(report["identity_mode"], "session-and-tool")

    def test_session_and_tool_rejects_pid_conflict(self):
        records = self.session_records()
        next(r for r in records if r["source"]["row"] == "tool-a")["fields"]["related_pid"] = 999
        decisions, _ = join_application(fixture_events(), records, fixture_scope(), "app", "session-and-tool")
        self.assertEqual(decisions[0]["status"], "uncertain")

    def test_session_and_tool_requires_observed_session(self):
        records = [r for r in self.session_records() if r["source"]["row"] != "llm-a"]
        decisions, _ = join_application(fixture_events(), records, fixture_scope(), "app", "session-and-tool")
        self.assertEqual(decisions[0]["status"], "abstain")

    def test_namespace_mismatch_is_not_a_pid_mapping(self):
        scope = fixture_scope(); scope.update(pid_namespace=None, clock_domain="uncalibrated", uncertainty_ms=None)
        records = fixture_records(); records[1]["fields"]["related_pid"] = 9001
        strict, _ = join_application(fixture_events(), records, scope, "app")
        shared, report = join_application(fixture_events(), records, scope, "app", "shared-tool-id")
        self.assertTrue(all(d["status"] == "abstain" for d in strict))
        self.assertTrue(all(d["status"] == "accepted" for d in shared))
        self.assertTrue(all(d["process_alignment_status"] == "not_evaluated_in_shared_id_mode" for d in shared))
        self.assertFalse(report["unified_trace_ready"])

    def test_shared_id_does_not_recover_missing_observation(self):
        records = [r for r in fixture_records() if r["source"]["row"] != "tool-a"]
        decisions, _ = join_application(fixture_events(), records, fixture_scope(), "app", "shared-tool-id")
        self.assertEqual([d["status"] for d in decisions], ["abstain", "accepted"])

    def test_shared_duplicate_remains_uncertain(self):
        records = fixture_records(); dup = copy.deepcopy(records[1]); dup["source"]["row"] = "duplicate"; records.append(dup)
        decisions, _ = join_application(fixture_events(), records, fixture_scope(), "app", "shared-tool-id")
        self.assertEqual(decisions[0]["status"], "uncertain")

    def test_shared_mode_still_requires_run_and_host(self):
        for key in ("run_id", "host_id", "boot_id"):
            scope = fixture_scope(); scope[key] = "different"
            decisions, _ = join_application(fixture_events(), fixture_records(), scope, "app", "shared-tool-id")
            self.assertTrue(all(d["status"] == "abstain" for d in decisions))


class NativeParserTests(unittest.TestCase):
    def make_inputs(self, root, missing_result=False, wrong_session=False):
        app = fixture_events()[0]
        launch = {"session_id": "native-session", "process": app["process"], "clock": app["clock"]}
        (root / "agent_a-launch.json").write_text(json.dumps(launch))
        rows = [{"type": "system", "subtype": "init", "session_id": "native-session"},
                {"type": "assistant", "session_id": "wrong" if wrong_session else "native-session",
                 "message": {"content": [{"type": "tool_use", "id": "actual-call-id", "name": "Write"}]}},
                {"type": "user", "session_id": "native-session",
                 "message": {"content": [{"type": "tool_result", "tool_use_id": "actual-call-id", "content": "ok"}]}},
                {"type": "result", "session_id": "native-session", "subtype": "success"}]
        if missing_result:
            rows.pop(2)
        (root / "claude-agent-a.log").write_text("".join(json.dumps(r) + "\n" for r in rows))
        (root / "agent_a-receipt-times.jsonl").write_text("".join(json.dumps({"line": i, "received_at_ms": 1100+i}) + "\n" for i in range(1,len(rows)+1)))
        out=root / "parsed"; out.mkdir()
        return out

    def test_native_tool_spans_preserve_id_and_raw_refs(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            root=Path(temp); out=self.make_inputs(root)
            events, refs, report=convert_agent(root, "agent_a", out)
            self.assertEqual(len(events),6)
            self.assertEqual([e["tool_call_id"] for e in events if e["event_type"]=="tool.start"],["actual-call-id"])
            self.assertEqual(len(refs),len(events))
            self.assertTrue(all(r["raw_refs"] for r in refs))

    def test_missing_native_tool_result_is_not_filled_in(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            root=Path(temp); out=self.make_inputs(root,missing_result=True)
            with self.assertRaises(ValueError): convert_agent(root,"agent_a",out)

    def test_native_session_mismatch_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            root=Path(temp); out=self.make_inputs(root,wrong_session=True)
            with self.assertRaises(ValueError): convert_agent(root,"agent_a",out)
