import unittest

from cost_ledger import deduplicate


class CostLedgerTests(unittest.TestCase):
    def test_same_session_is_counted_once_and_keeps_largest_final_cost(self):
        entries = [
            {"path": "partial.log", "session_id": "s1", "cost_usd": 0.1},
            {"path": "copy.log", "session_id": "s1", "cost_usd": 0.1},
            {"path": "final.log", "session_id": "s1", "cost_usd": 0.2},
        ]
        unique, duplicates = deduplicate(entries)
        self.assertEqual(duplicates, 2)
        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0]["path"], "final.log")
        self.assertEqual(unique[0]["cost_usd"], 0.2)
        self.assertEqual(unique[0]["duplicate_paths"], ["copy.log", "partial.log"])


if __name__ == "__main__":
    unittest.main()
