import tempfile
from pathlib import Path
import unittest

from capture_public_dataset_replay import public_input
from public_dataset_runtime_probe import summarize


class PublicDatasetReplayInputTests(unittest.TestCase):
    @staticmethod
    def keys(value):
        if isinstance(value, dict):
            for key, child in value.items():
                yield key
                yield from PublicDatasetReplayInputTests.keys(child)
        elif isinstance(value, list):
            for child in value:
                yield from PublicDatasetReplayInputTests.keys(child)

    def test_pinned_samples_are_label_isolated(self):
        cases = (
            ("AgentTrace", "cod_034b23", ("root_cause_node_id", "error_node_id", "causal_path", "bug_description")),
            ("WhoAndWhen", "99da66d8af02491f98b98c56b26c709e773b5a2ad945fb280375951ba600de09",
             ("mistake_agent", "mistake_step", "mistake_reason", "ground_truth")),
            ("TRAIL", "0035f455b3ff2295167a844f04d85d34", ("errors", "evidence", "description")),
        )
        for dataset, sample_id, forbidden in cases:
            with self.subTest(dataset=dataset):
                value, provenance = public_input(dataset, sample_id)
                observed_keys = set(self.keys(value))
                self.assertTrue(observed_keys.isdisjoint(forbidden))
                self.assertEqual(provenance["dataset"], dataset)
                self.assertFalse(provenance["historical_annotation_used_as_runtime_input"])
                self.assertGreater(summarize(value)["item_count"], 0)

    def test_only_preselected_sample_is_accepted(self):
        with self.assertRaisesRegex(ValueError, "preselected"):
            public_input("AgentTrace", "another-case")


if __name__ == "__main__":
    unittest.main()
