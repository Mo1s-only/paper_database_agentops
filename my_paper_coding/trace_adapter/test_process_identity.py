import unittest

from process_identity import decide_pid_mapping


def candidate(observer, local, namespace="pid:[child]", direct=True, indirect=False):
    return {
        "observer_pid": observer,
        "observer_pid_namespace": "pid:[observer]",
        "process_pid_namespace": namespace,
        "nspid_vector": [observer, local] if direct else None,
        "indirect_match": indirect,
    }


class ProcessIdentityTests(unittest.TestCase):
    def test_unique_nspid_truth_is_accepted(self):
        result = decide_pid_mapping(1, "pid:[child]", [candidate(100, 1)])
        self.assertEqual(result["mapping_status"], "accepted")
        self.assertEqual(result["mapping_method"], "proc_status_nspid")

    def test_same_local_pid_without_namespace_abstains(self):
        values = [candidate(100, 1, "pid:[a]"), candidate(200, 1, "pid:[b]")]
        result = decide_pid_mapping(1, None, values)
        self.assertEqual(result["mapping_status"], "abstain")
        self.assertEqual(result["candidate_count"], 2)

    def test_even_one_direct_candidate_needs_local_namespace(self):
        result = decide_pid_mapping(1, None, [candidate(100, 1, "pid:[a]")])
        self.assertEqual(result["mapping_status"], "abstain")
        self.assertEqual(result["reason"], "local_pid_namespace_missing")

    def test_namespace_disambiguates_same_local_pid(self):
        values = [candidate(100, 1, "pid:[a]"), candidate(200, 1, "pid:[b]")]
        result = decide_pid_mapping(1, "pid:[b]", values)
        self.assertEqual(result["mapping_status"], "accepted")
        self.assertEqual(result["observer_pid"], 200)

    def test_unique_indirect_evidence_remains_inferred(self):
        values = [candidate(1758, 81, direct=False, indirect=True)]
        result = decide_pid_mapping(81, "pid:[app]", values,
                                    ["shared_tool_call_id", "launch_interval"])
        self.assertEqual(result["mapping_status"], "inferred")

    def test_missing_or_conflicting_indirect_evidence_abstains(self):
        values = [candidate(100, 1, direct=False, indirect=True),
                  candidate(200, 1, direct=False, indirect=True)]
        self.assertEqual(decide_pid_mapping(1, None, values, ["session"])["mapping_status"],
                         "abstain")
        self.assertEqual(decide_pid_mapping(1, None, [], ["session"])["mapping_status"],
                         "abstain")


if __name__ == "__main__":
    unittest.main()
