"""Behavioral regression tests; synthetic fixtures are not experimental evidence."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from align_candidates import align, load_evidence, sha256


def event(kind, row, pid=None, timestamp=50, **fields):
    return {"record_type": f"agentsight.{kind}", "evidence_status": "observed",
            "timestamp": timestamp, "pid": pid, "fields": fields,
            "source": {"path": "capture.db", "table": kind, "row": row, "role": "raw_observation"}}


def fixtures():
    return [event("process_nodes", "p", 7, start_timestamp_ms=0, end_timestamp_ms=100),
            event("tool_calls", "t", related_pid=7, tool_call_id="call-x")]


def decision(records, relation="tool_calls_process"):
    return next(d for d in align(records, "test")[0] if d["relation"] == relation)


class AssociationTests(unittest.TestCase):
    def test_pid_with_bounded_lifetime(self):
        self.assertEqual(decision(fixtures())["status"], "accepted")

    def test_missing_pid_abstains(self):
        records = fixtures()
        records[1]["fields"].pop("related_pid")
        self.assertEqual(decision(records)["status"], "abstain")

    def test_missing_timestamp_uncertain(self):
        records = fixtures()
        records[1]["timestamp"] = None
        self.assertEqual(decision(records)["status"], "uncertain")

    def test_shift_outside_lifetime_abstains(self):
        records = fixtures()
        records[1]["timestamp"] = 150
        result = decision(records)
        self.assertEqual(result["status"], "abstain")
        self.assertEqual(result["reason"], "timestamp_conflict")
        self.assertEqual(len(result["rejected_candidates"]), 1)

    def test_reused_pid_uses_lifetime(self):
        records = fixtures() + [event("process_nodes", "p2", 7, start_timestamp_ms=101, end_timestamp_ms=200)]
        result = decision(records)
        self.assertEqual(result["status"], "accepted")
        self.assertTrue(result["candidates"][0]["target_ref"].endswith("/p"))

    def test_overlapping_pid_is_uncertain(self):
        records = fixtures() + [event("process_nodes", "p2", 7, start_timestamp_ms=25, end_timestamp_ms=75)]
        self.assertEqual(decision(records)["status"], "uncertain")

    def test_unknown_lifetime_competitor_prevents_acceptance(self):
        records = fixtures() + [event("process_nodes", "p2", 7, start_timestamp_ms=0)]
        self.assertEqual(decision(records)["status"], "uncertain")

    def test_structured_tool_id(self):
        records = fixtures() + [event("llm_calls", "l", 7,
            response_body_json=json.dumps({"content": [{"type": "tool_use", "id": "call-x"}]}))]
        self.assertEqual(decision(records, "tool_llm")["status"], "accepted")

    def test_pid_conflict_overrides_tool_id(self):
        records = fixtures() + [event("llm_calls", "l", 8,
            response_body_json=json.dumps({"content": [{"type": "tool_use", "id": "call-x"}]}))]
        self.assertEqual(decision(records, "tool_llm")["status"], "uncertain")

    def test_duplicate_tool_id_is_uncertain(self):
        records = fixtures() + [event("llm_calls", row, 7,
            response_body_json=json.dumps({"content": [{"type": "tool_use", "id": "call-x"}]}))
            for row in ("l1", "l2")]
        self.assertEqual(decision(records, "tool_llm")["status"], "uncertain")

    def test_temporal_proximity_not_identity(self):
        records = fixtures() + [event("llm_calls", "l", 7, response_body_json='{"text":"call-x"}')]
        self.assertEqual(decision(records, "tool_llm")["status"], "uncertain")

    def test_nested_tool_arguments_cannot_invent_a_call(self):
        records = fixtures() + [event("llm_calls", "l", 7,
            response_body_json=json.dumps({"content": [{"type": "tool_use", "id": "different",
                "input": {"example": {"type": "tool_use", "id": "call-x"}}}]}))]
        self.assertEqual(decision(records, "tool_llm")["status"], "uncertain")

    def test_no_agent_assignment_from_final_summary_or_filename(self):
        app = {"record_type": "application.result", "evidence_status": "observed", "session_id": "s",
               "agent_id": "agent_b", "source": {"path": "claude-agent-b.log", "line": 1, "role": "app_log"}}
        decisions, trace, summary = align(fixtures() + [app], "test")
        self.assertEqual(decisions[-1]["status"], "abstain")
        self.assertTrue(all(r["agent_id"] is None for r in trace))
        self.assertIsNone(summary["precision"])
        self.assertFalse(summary["unified_trace_ready"])

    def test_derived_and_validator_do_not_change_prediction(self):
        injected = copy.deepcopy(fixtures()[1])
        injected["evidence_status"] = "derived_untrusted"
        injected["source"]["role"] = "derived"
        oracle = copy.deepcopy(injected)
        oracle["evidence_status"] = "observed"
        oracle["source"]["role"] = "validator"
        self.assertEqual(align(fixtures(), "test"), align(fixtures() + [injected, oracle], "test"))


class InputGateTests(unittest.TestCase):
    def test_hash_gate_and_validator_not_opened(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "capture.db"
            raw.write_bytes(b"fixture")
            manifest = root / "run.json"
            manifest.write_text(json.dumps({"run_id": "test", "artifacts": [
                {"path": "capture.db", "category": "raw_observation", "sha256": sha256(raw)},
                {"path": "nonexistent-truth.json", "category": "validator", "sha256": "unused"}]}))
            evidence = root / "evidence.jsonl"
            evidence.write_text(json.dumps(fixtures()[0]) + "\n")
            _, rows, audit = load_evidence(manifest, evidence, root)
            self.assertEqual(len(rows), 1)
            self.assertFalse(audit["validator_artifacts_read"])
            raw.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                load_evidence(manifest, evidence, root)

    def test_duplicate_locator_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "capture.db"
            raw.write_bytes(b"fixture")
            manifest = root / "run.json"
            manifest.write_text(json.dumps({"artifacts": [
                {"path": "capture.db", "category": "raw_observation", "sha256": sha256(raw)}]}))
            evidence = root / "evidence.jsonl"
            evidence.write_text((json.dumps(fixtures()[0]) + "\n") * 2)
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                load_evidence(manifest, evidence, root)

    def test_validator_cannot_masquerade_as_observation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "run.json"
            manifest.write_text(json.dumps({"artifacts": [
                {"path": "capture.db", "category": "validator", "sha256": "unused"}]}))
            evidence = root / "evidence.jsonl"
            evidence.write_text(json.dumps(fixtures()[0]) + "\n")
            _, records, audit = load_evidence(manifest, evidence, root)
            self.assertEqual(records, [])
            self.assertEqual(audit["verified_sources"], {})

    def test_malformed_input_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "run.json"
            manifest.write_text('{"artifacts": []}')
            evidence = root / "evidence.jsonl"
            evidence.write_text('{broken}\n')
            with self.assertRaises(ValueError):
                load_evidence(manifest, evidence, root)

    def test_existing_output_is_never_overwritten(self):
        from align_candidates import run
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileExistsError):
                run(Path("not-read.json"), Path("not-read.jsonl"), Path(temp))

    def test_smoke_missing_capture_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as temp:
            evidence = Path(temp) / "evidence.jsonl"
            evidence.write_text("")
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("smoke_check.py")),
                temp, "--normalized", str(evidence)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(json.loads(result.stdout)["input_gate"]["passed"])
            self.assertFalse((Path(temp) / "adapter-smoke-report.json").exists())


if __name__ == "__main__":
    unittest.main()
