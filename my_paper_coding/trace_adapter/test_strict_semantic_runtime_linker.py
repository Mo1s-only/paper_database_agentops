from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from strict_semantic_runtime_linker import align


class StrictSemanticRuntimeLinkerTests(unittest.TestCase):
    def write_jsonl(self, path: Path, rows: list[dict]) -> None:
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def make_run(self, root: Path, *, duplicate_exec: bool = False, wrong_namespace: bool = False,
                 event_mono_ns: int = 105_000_000) -> Path:
        run = root / "run"
        run.mkdir()
        agent_pid = 476
        self.write_jsonl(run / "agent_a-receipt-times.jsonl", [
            {"line": 1, "received_at_ms": 1000}, {"line": 2, "received_at_ms": 1010},
        ])
        self.write_jsonl(run / "claude-agent-a.log", [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "tool-1", "name": "Bash", "input": {"command": "python3 /tmp/unique_task.py"}}
            ]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "tool-1", "content": "ok"}
            ]}},
        ])
        (run / "agent_a-launch.json").write_text(json.dumps({"pid": agent_pid}), encoding="utf-8")
        anchor = {"source": "diagnostic", "data": {"event": "CLOCK_SYNC", "phase": "start",
                   "wall_time_ns": 1_000_000_000, "mono_ns": 100_000_000,
                   "_agentsight_clock": {"anchor_uncertainty_ns": 1_000_000}}}
        root_event = {"source": "process", "pid": 10, "data": {"event": "EXEC", "ppid": 1,
                       "namespace_pid": agent_pid, "filename": "/usr/bin/claude", "full_command": "claude -p x",
                       "timestamp": 100_000_000}}
        child = {"source": "process", "pid": 11, "data": {"event": "EXEC", "ppid": 10,
                 "namespace_pid": 501, "filename": "/usr/bin/python3", "full_command": "python3 /tmp/unique_task.py",
                 "timestamp": event_mono_ns}}
        if wrong_namespace:
            root_event["data"]["namespace_pid"] = 999
        events = [anchor, root_event, child]
        if duplicate_exec:
            duplicate = json.loads(json.dumps(child))
            duplicate["pid"] = 12
            duplicate["data"]["timestamp"] = 106_000_000
            events.append(duplicate)
        self.write_jsonl(run / "raw-stream.log", events)
        with closing(sqlite3.connect(run / "session.db")) as connection:
            connection.execute("CREATE TABLE audit_events (id TEXT, timestamp_ms INTEGER, pid INTEGER, target TEXT, action TEXT, details_json TEXT, audit_type TEXT)")
        return run

    def test_unique_command_time_and_pid_ancestry_is_linked_as_inference(self):
        with tempfile.TemporaryDirectory() as temp:
            report = align(self.make_run(Path(temp)))
        self.assertEqual(report["unique_runtime_candidates"], 1)
        self.assertEqual(report["links"][0]["link_status"], "unique_runtime_candidate")
        self.assertFalse(report["links"][0]["direct_shared_tool_id"])

    def test_ambiguous_process_candidates_abstain(self):
        with tempfile.TemporaryDirectory() as temp:
            report = align(self.make_run(Path(temp), duplicate_exec=True))
        self.assertEqual(report["links"][0]["link_status"], "abstain")
        self.assertEqual(report["links"][0]["candidate_count"], 2)

    def test_unmapped_agent_root_abstains(self):
        with tempfile.TemporaryDirectory() as temp:
            report = align(self.make_run(Path(temp), wrong_namespace=True))
        self.assertEqual(report["links"][0]["link_status"], "abstain")
        self.assertFalse(report["links"][0]["checks"]["unique_claude_pid_namespace_root"])

    def test_event_inside_anchor_uncertainty_at_span_boundary_abstains(self):
        with tempfile.TemporaryDirectory() as temp:
            report = align(self.make_run(Path(temp), event_mono_ns=100_500_000))
        self.assertEqual(report["links"][0]["link_status"], "abstain")


if __name__ == "__main__":
    unittest.main()
