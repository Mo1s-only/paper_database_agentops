import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from align_candidates import ROOT, load_evidence
from audit_real_api_cost_ledger import extract_cost
from evaluate_public_dataset_mapping import evaluate
from normalize_trail_public_spans import ARCHIVE, normalize
from prepare_public_dataset_subset import prepare


class PublicDatasetSubsetTests(unittest.TestCase):
    def test_curated_subset_preserves_labels_without_fabricating_runtime_evidence(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            output = Path(temp) / "subset"
            report = prepare(output)
            cases = [json.loads(line) for line in (output / "selected-cases.jsonl")
                     .read_text(encoding="utf-8").splitlines()]
            manifest = json.loads((output / "subset-manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(report["selected_case_count"], 5)
        self.assertEqual(report["cases_by_dataset"], {"AgentTrace": 1, "WhoAndWhen": 2, "TRAIL": 2})
        self.assertEqual(len(manifest["source_artifacts"]), 4)
        for case in cases:
            self.assertEqual(case["evidence_role"], "public_dataset_annotation_or_trace_not_runtime_observation")
            self.assertEqual(case["runtime_evidence"]["status"], "not_present_in_selected_public_artifact")
            self.assertIsNone(case["runtime_evidence"]["ebpf_pid_lineage"])
            self.assertEqual(len(case["selected_record_sha256"]), 64)
        agent_trace = next(case for case in cases if case["dataset"] == "AgentTrace")
        self.assertTrue(agent_trace["gold_labels"]["root_cause_node_id"])
        self.assertEqual(agent_trace["available_identity_fields"]["tool_call_id"], False)
        who_and_when = [case for case in cases if case["dataset"] == "WhoAndWhen"]
        self.assertEqual({case["split"] for case in who_and_when}, {"Algorithm-Generated", "Hand-Crafted"})
        trail = [case for case in cases if case["dataset"] == "TRAIL"]
        self.assertTrue(all(case["structure"]["error_count"] > 1 for case in trail))
        self.assertTrue(all(case["available_identity_fields"]["agent_id"] is False for case in trail))
        self.assertEqual(
            {case["split"]: (case["public_trace_join"]["annotation_location_match_count"],
                             case["public_trace_join"]["annotation_location_count"],
                             case["public_trace_join"]["span_count"])
             for case in trail},
            {"GAIA": (3, 3, 11), "SWE-bench": (8, 8, 32)},
        )
        self.assertTrue(all(case["public_trace_join"]["all_annotations_resolve_to_span_id"]
                            for case in trail))
        self.assertTrue(all(case["public_trace_join"]["evidence_role"] ==
                            "historical_public_semantic_trace_not_current_ebpf_observation"
                            for case in trail))

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            output = Path(temp) / "existing"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("preserve", encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "Refusing to replace"):
                prepare(output)
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    def test_trail_spans_normalize_without_claiming_runtime_identity(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            root = Path(temp)
            subset_dir = root / "subset"
            prepare(subset_dir)
            normalized_path = root / "trail-spans.jsonl"
            report = normalize(ARCHIVE, normalized_path)
            spans = [json.loads(line) for line in normalized_path.read_text(encoding="utf-8").splitlines()]
            cases = [json.loads(line) for line in (subset_dir / "selected-cases.jsonl")
                     .read_text(encoding="utf-8").splitlines() if json.loads(line)["dataset"] == "TRAIL"]

        self.assertEqual(report["record_count"], 43)
        self.assertEqual({case["split"]: case["span_count"] for case in report["cases"]},
                         {"GAIA": 11, "SWE-bench": 32})
        self.assertEqual(len({span["span_id"] for span in spans}), 43)
        self.assertTrue(all(span["record_type"] == "public.semantic_span" for span in spans))
        self.assertTrue(all(span["evidence_status"] == "historical_public_trace" for span in spans))
        self.assertTrue(all(all(value is None for value in span["identity"].values()) for span in spans))
        spans_by_split = {}
        for span in spans:
            spans_by_split.setdefault(span["split"], set()).add(span["span_id"])
        for case in cases:
            gold_ids = {error["location"] for error in case["gold_labels"]["errors"]}
            self.assertTrue(gold_ids.issubset(spans_by_split[case["split"]]))

    def test_runtime_aligner_fail_closes_on_historical_public_trace(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            root = Path(temp)
            spans_path = root / "trail-spans.jsonl"
            normalize(ARCHIVE, spans_path)
            manifest_path = root / "run.json"
            archive_rel = ARCHIVE.resolve().relative_to(ROOT.resolve()).as_posix()
            archive_sha = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps({"run_id": "trail-public-only", "artifacts": [
                {"path": archive_rel, "category": "raw_observation", "sha256": archive_sha}
            ]}), encoding="utf-8")
            _, admitted, audit = load_evidence(manifest_path, spans_path)

        self.assertEqual(admitted, [])
        self.assertEqual(audit["excluded_records"], {"not_observed_or_not_allowlisted": 43})

    def test_isolated_public_label_evaluator_reports_supported_claims_by_family(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            output = Path(temp) / "evaluation.json"
            report = evaluate(output=output)

        self.assertEqual(report["case_count"], 5)
        self.assertEqual(report["source_integrity_verified_count"], 5)
        by_case = {(row["dataset"], row.get("split")): row for row in report["case_results"]}
        agent_trace = by_case[("AgentTrace", None)]
        self.assertEqual(agent_trace["path_nodes_resolved"], 3)
        self.assertEqual(agent_trace["path_edges_resolved"], 2)
        who_cases = [row for row in report["case_results"] if row["dataset"] == "WhoAndWhen"]
        self.assertEqual(len(who_cases), 2)
        self.assertTrue(all(row["label_fields_present"] == row["label_fields_expected"] == 4 for row in who_cases))
        self.assertTrue(all(row["explicit_history_step_locator_available"] is False for row in who_cases))
        trail_cases = [row for row in report["case_results"] if row["dataset"] == "TRAIL"]
        self.assertEqual({row["split"]: (row["gold_locations_resolved"], row["gold_locations_total"])
                          for row in trail_cases}, {"GAIA": (3, 3), "SWE-bench": (8, 8)})

    def test_cost_audit_extracts_cost_without_credentials(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            run_dir = Path(temp) / "real-canary-test"
            run_dir.mkdir()
            summary = run_dir / "diagnostic-summary.json"
            summary.write_text(json.dumps({"real_api": True, "sessions": 1,
                "cli": {"reported_cost_usd": 0.0123}, "cost_status": "within_session_limit"}),
                encoding="utf-8")
            result = extract_cost(run_dir)

        self.assertEqual(result["reported_cost_usd"], 0.0123)
        self.assertTrue(result["cost_complete"])
        self.assertTrue(result["real_api_evidence"])
        self.assertEqual(len(result["cost_summary_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
