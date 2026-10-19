from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .agenttrace_adapter import adapt_file as adapt_agenttrace
from .trail_adapter import adapt_entries as adapt_trail
from .validation import validate_record
from .who_when_adapter import adapt_file as adapt_who_when


class AdapterTests(unittest.TestCase):
    def assert_schema_valid(self, record: dict) -> None:
        self.assertEqual([], validate_record(record))

    def test_who_when_preserves_direct_labels_and_abstains_on_edges(self) -> None:
        obj = {
            "is_correct": False,
            "question_ID": "q-1",
            "history": [
                {"name": "planner", "role": "assistant", "content": "plan"},
                {"name": "tool", "role": "user", "content": "bad result"},
            ],
            "mistake_agent": "planner",
            "mistake_step": "0",
            "mistake_reason": "bad plan",
            "system_prompt": {"planner": "prompt"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "Algorithm-Generated"
            folder.mkdir()
            path = folder / "1.json"
            path.write_text(json.dumps(obj), encoding="utf-8")
            record = adapt_who_when(path, root)
        self.assertEqual("direct", record["truth"]["responsibility_agents"]["state"])
        self.assertEqual(["history:0"], record["truth"]["responsibility_steps"]["values"])
        self.assertEqual("abstain", record["truth"]["propagation_edges"]["state"])
        self.assertEqual(1, record["quality"]["relations_reconstructed"])
        self.assert_schema_valid(record)

    def test_trail_keeps_error_span_partial(self) -> None:
        raw = {
            "trace_id": "trace-1",
            "spans": [
                {
                    "span_id": "root",
                    "parent_span_id": "",
                    "service_name": "agent-a",
                    "span_name": "root",
                    "timestamp": "1",
                    "child_spans": [
                        {
                            "span_id": "child",
                            "parent_span_id": "root",
                            "service_name": "agent-b",
                            "span_name": "tool",
                            "timestamp": "2",
                            "child_spans": [],
                        }
                    ],
                }
            ],
        }
        annotation = {
            "trace_id": "trace-1",
            "errors": [{"location": "child", "category": "Tool Error", "impact": "HIGH"}],
            "scores": [],
        }
        record = adapt_trail(
            zip_name="trail.zip",
            raw_name="benchmarking/data/GAIA/trace-1.json",
            raw_bytes=json.dumps(raw).encode(),
            annotation_name="benchmarking/processed_annotations_gaia/trace-1.json",
            annotation_bytes=json.dumps(annotation).encode(),
        )
        self.assertEqual("partial", record["truth"]["responsibility_steps"]["state"])
        self.assertEqual("abstain", record["truth"]["root_cause_nodes"]["state"])
        self.assertEqual(1, record["quality"]["relations_reconstructed"])
        self.assert_schema_valid(record)

    def test_agenttrace_maps_path_to_explicit_edges(self) -> None:
        graph = {
            "run_id": "run-1",
            "nodes": [
                {"id": "n1", "agent_id": "a", "type": "error", "timestamp": "1", "data": {"step": 1}},
                {"id": "n2", "agent_id": "b", "type": "decision", "timestamp": "2", "data": {"step": 2}},
            ],
            "edges": [{"id": "e1", "source_id": "n1", "target_id": "n2", "type": "data_flow"}],
        }
        outer = {
            "scenario_id": "cod_test",
            "trace_json": json.dumps(graph),
            "root_cause_node_id": "n1",
            "error_node_id": "n2",
            "causal_path": ["n1", "n2"],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "traces").mkdir()
            path = root / "traces" / "cod_test_trace.json"
            path.write_text(json.dumps(outer), encoding="utf-8")
            record = adapt_agenttrace(path, root)
        self.assertEqual("direct", record["truth"]["root_cause_nodes"]["state"])
        self.assertEqual("derived", record["truth"]["responsibility_agents"]["state"])
        self.assertEqual("derived", record["truth"]["propagation_edges"]["state"])
        self.assertEqual("direct", record["truth"]["causal_paths"]["state"])
        self.assert_schema_valid(record)

    def test_trail_repairs_only_trailing_commas_and_records_warning(self) -> None:
        raw = b'{"trace_id":"t","spans":[]}'
        annotation = b'{"trace_id":"t","errors":[],"scores":[],}'
        record = adapt_trail(
            zip_name="trail.zip",
            raw_name="benchmarking/data/GAIA/t.json",
            raw_bytes=raw,
            annotation_name="benchmarking/processed_annotations_gaia/t.json",
            annotation_bytes=annotation,
        )
        self.assertTrue(any("trailing-comma" in warning for warning in record["quality"]["warnings"]))
        self.assert_schema_valid(record)


if __name__ == "__main__":
    unittest.main()
