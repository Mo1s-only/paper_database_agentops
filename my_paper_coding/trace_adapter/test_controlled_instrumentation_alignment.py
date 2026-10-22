import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from align_candidates import ROOT
from application_events import EventWriter
from controlled_instrumentation_alignment import run


class ControlledInstrumentationAlignmentTests(unittest.TestCase):
    def make_run(self, root: Path, include_marker: bool = True, duplicate_system_id: bool = False):
        run_dir = root / "run-fixture"
        run_dir.mkdir()
        tool_id = "call_fixture_exact"
        (run_dir / "plan.json").write_text(json.dumps({
            "run_id": run_dir.name,
            "tool_id_bridge": {"enabled": True, "mode": "controlled_hook_instrumentation"},
        }), encoding="utf-8")
        (run_dir / "claude-agent-a.log").write_text(json.dumps({
            "type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": tool_id, "name": "Bash"},
            ]},
        }) + "\n", encoding="utf-8")
        (run_dir / "agent_a-tool-call-hook-events.jsonl").write_text("".join(
            json.dumps(event) + "\n" for event in [
                {"hook_event_name": "PreToolUse", "tool_call_id": tool_id,
                 "command_tagged": include_marker},
                {"hook_event_name": "PostToolUse", "tool_call_id": tool_id},
            ]), encoding="utf-8")
        with closing(sqlite3.connect(run_dir / "session.db")) as connection:
            connection.execute("CREATE TABLE tool_calls (tool_call_id TEXT)")
            connection.execute("CREATE TABLE process_nodes (pid INTEGER, ppid INTEGER, comm TEXT, command TEXT)")
            connection.execute("INSERT INTO tool_calls VALUES (?)", (tool_id,))
            if duplicate_system_id:
                connection.execute("INSERT INTO tool_calls VALUES (?)", (tool_id,))
            connection.executemany("INSERT INTO process_nodes VALUES (?, ?, ?, ?)", [
                (100, 10, "bash", "tagged wrapper"), (101, 100, "python3", "scenario_service_observer.py")])
            connection.commit()
        marker = f"AGENTOPS_TOOL_CALL_ID={tool_id}" if include_marker else ""
        bpf = [
            {"source": "process", "pid": 100, "data": {"event": "EXEC", "filename": "/usr/bin/bash",
             "full_command": f"{marker} bash -c python3 scenario_service_observer.py", "ppid": 10}},
            {"source": "process", "pid": 101, "data": {"event": "EXEC", "filename": "/usr/bin/python3",
             "full_command": "python3 scenario_service_observer.py", "ppid": 100}},
        ]
        (run_dir / "raw-stream.log").write_text("".join(json.dumps(row) + "\n" for row in bpf), encoding="utf-8")

        app_path = run_dir / "parsed" / "application-events.jsonl"
        app_path.parent.mkdir()
        writer = EventWriter(app_path, run_dir.name, "session-fixture", "agent_a", {
            "host_id": "host-fixture", "boot_id": "boot-fixture", "pid_namespace": "pid:[1]",
            "pid": 20, "start_ms": 1,
        }, {"domain": "fixture-clock", "uncertainty_ms": 0})
        writer.emit("session.start", timestamp_ms=1)
        writer.emit("step.start", step_id="step-fixture", timestamp_ms=2)
        writer.emit("tool.start", step_id="step-fixture", tool_call_id=tool_id, timestamp_ms=3)
        writer.emit("tool.end", step_id="step-fixture", tool_call_id=tool_id, timestamp_ms=4)
        writer.emit("step.end", step_id="step-fixture", timestamp_ms=5)
        writer.emit("session.end", timestamp_ms=6)
        writer.finish()
        return run_dir, app_path

    def test_exact_hook_agentsight_and_ebpf_evidence_accepts_only_controlled_profile(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            run_dir, app = self.make_run(Path(temp))
            summary = run(run_dir, app, run_dir / "new-controlled-profile")
            row = json.loads((run_dir / "new-controlled-profile" / "application-process-alignments.jsonl")
                             .read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(summary["status_counts"], {"accepted": 1})
        self.assertEqual(row["status"], "accepted")
        self.assertEqual(row["relation_type"], "controlled_instrumentation.tool_to_runtime_process_lineage")
        self.assertFalse(row["responsibility_claim"])
        self.assertTrue(any("session.db#tool_calls/" in ref for ref in row["evidence_refs"]))
        self.assertTrue(any("raw-stream.log#line=" in ref for ref in row["evidence_refs"]))

    def test_missing_marker_abstains_even_when_semantic_tool_id_exists(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            run_dir, app = self.make_run(Path(temp), include_marker=False)
            summary = run(run_dir, app, run_dir / "new-controlled-profile")
            row = json.loads((run_dir / "new-controlled-profile" / "application-process-alignments.jsonl")
                             .read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(summary["status_counts"], {"abstain": 1})
        self.assertEqual(row["reason"], "controlled_instrumentation_evidence_incomplete")

    def test_duplicate_agentsight_tool_id_does_not_accept(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            run_dir, app = self.make_run(Path(temp), duplicate_system_id=True)
            summary = run(run_dir, app, run_dir / "new-controlled-profile")
            row = json.loads((run_dir / "new-controlled-profile" / "application-process-alignments.jsonl")
                             .read_text(encoding="utf-8").splitlines()[0])
            audit = json.loads((run_dir / "new-controlled-profile" / "tool-id-process-audit.json")
                               .read_text(encoding="utf-8"))
        self.assertEqual(summary["status_counts"], {"abstain": 1})
        self.assertEqual(audit["tool_links"][0]["agentsight_tool_match_count"], 2)
        self.assertEqual(row["reason"], "controlled_instrumentation_evidence_incomplete")

    def test_run_without_explicit_instrumentation_flag_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            run_dir, app = self.make_run(Path(temp))
            plan = json.loads((run_dir / "plan.json").read_text(encoding="utf-8"))
            plan["tool_id_bridge"]["enabled"] = False
            (run_dir / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not explicitly enable"):
                run(run_dir, app, run_dir / "new-controlled-profile")


if __name__ == "__main__":
    unittest.main()
