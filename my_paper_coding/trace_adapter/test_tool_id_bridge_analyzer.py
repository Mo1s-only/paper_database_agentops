import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from analyze_scenario_tool_id_bridge import analyze


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class ToolIdBridgeAnalyzerTests(unittest.TestCase):
    def make_run(self, root: Path, include_markers: bool) -> Path:
        run = root / "run-fixture"
        run.mkdir()
        ids = {"agent_a": "call_fixture_A", "agent_b": "call_fixture_B"}
        for agent, suffix in (("agent_a", "a"), ("agent_b", "b")):
            write_jsonl(run / f"claude-agent-{suffix}.log", [{
                "type": "assistant",
                "message": {"content": [{"type": "tool_use", "id": ids[agent], "name": "Bash"}]},
            }])
            write_jsonl(run / f"{agent}-tool-call-hook-events.jsonl", [
                {"hook_event_name": "PreToolUse", "tool_call_id": ids[agent],
                 "command_tagged": include_markers},
                {"hook_event_name": "PostToolUse", "tool_call_id": ids[agent]},
            ])

        with closing(sqlite3.connect(run / "session.db")) as connection:
            connection.execute("CREATE TABLE tool_calls (tool_call_id TEXT, tool_name TEXT)")
            connection.execute("CREATE TABLE process_nodes (pid INTEGER, ppid INTEGER, comm TEXT, command TEXT)")
            for tool_id in ids.values():
                connection.execute("INSERT INTO tool_calls VALUES (?, ?)", (tool_id, "Bash"))
            for pid, parent, comm, command in (
                (100, 10, "bash", "tagged shell A"),
                (101, 100, "python3", "scenario_service_observer.py"),
                (200, 20, "bash", "tagged shell B"),
                (201, 200, "python3", "scenario_service_decider.py"),
            ):
                connection.execute("INSERT INTO process_nodes VALUES (?, ?, ?, ?)",
                                   (pid, parent, comm, command))
            connection.commit()

        events = []
        for tool_id, carrier, child, script in (
            (ids["agent_a"], 100, 101, "scenario_service_observer.py"),
            (ids["agent_b"], 200, 201, "scenario_service_decider.py"),
        ):
            command = f"AGENTOPS_TOOL_CALL_ID={tool_id} -c {script}" if include_markers else f"bash -c {script}"
            if include_markers:
                events.append({"source": "process", "pid": carrier, "data": {
                    "event": "EXEC", "filename": "/usr/bin/bash", "full_command": command,
                    "ppid": 10 if carrier == 100 else 20,
                }})
            events.append({"source": "process", "pid": child, "data": {
                "event": "EXEC", "filename": "/usr/bin/python3", "full_command": f"python3 {script}",
                "ppid": carrier,
            }})
        write_jsonl(run / "raw-stream.log", events)
        return run

    def test_interleaved_ids_link_only_to_their_own_process_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            result = analyze(self.make_run(Path(temp), include_markers=True))
        links = {item["tool_call_id"]: item for item in result["tool_links"]}
        self.assertEqual(result["exact_native_agentsight_tool_id_matches"], 2)
        self.assertEqual(links["call_fixture_A"]["status"], "direct_instrumented_id_to_process_lineage")
        self.assertEqual(links["call_fixture_B"]["status"], "direct_instrumented_id_to_process_lineage")
        self.assertEqual([item["pid"] for item in links["call_fixture_A"]["ebpf_linked_scenario_child_execs"]], [101])
        self.assertEqual([item["pid"] for item in links["call_fixture_B"]["ebpf_linked_scenario_child_execs"]], [201])

    def test_uninstrumented_candidates_never_become_direct(self):
        with tempfile.TemporaryDirectory() as temp:
            result = analyze(self.make_run(Path(temp), include_markers=False))
        self.assertEqual(result["exact_native_agentsight_tool_id_matches"], 2)
        self.assertTrue(all(item["status"] == "semantic_id_only" for item in result["tool_links"]))
        self.assertTrue(all(not item["ebpf_exact_id_carrier_pids"] for item in result["tool_links"]))


if __name__ == "__main__":
    unittest.main()
