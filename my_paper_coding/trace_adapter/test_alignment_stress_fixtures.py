import unittest

from generate_alignment_stress_fixtures import CATEGORIES, generate


class AlignmentStressFixtureTests(unittest.TestCase):
    def test_thousand_deterministic_cases_have_expected_fail_closed_decisions(self):
        fixtures, summary = generate(1000)
        self.assertEqual(len(fixtures), 1000)
        self.assertEqual(set(summary["category_counts"]), set(CATEGORIES))
        self.assertEqual(summary["expected_status_mismatches"], [])
        self.assertEqual(summary["api_calls"], 0)
        self.assertFalse(summary["production_aligner_exercised"])
        self.assertEqual(summary["decision_counts"].get("accepted"), 112)
        self.assertEqual(summary["decision_counts"].get("abstain"), 111)
        self.assertEqual(summary["decision_counts"].get("uncertain"), 777)


if __name__ == "__main__":
    unittest.main()
