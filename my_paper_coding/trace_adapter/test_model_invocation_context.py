import copy
import unittest

from model_invocation_context import VERSION, validate_context, validate_contexts


def context():
    return {
        "schema_version": VERSION,
        "evidence_kind": "runtime_observed",
        "run_id": "run",
        "session_id": "session",
        "agent_id": "agent",
        "request_id": "request",
        "response_id": "response",
        "model_id": "model",
        "model_version": "version",
        "sampling_temperature": 0.0,
        "sampling_top_p": 1.0,
        "system_prompt_sha256": "a" * 64,
        "tool_schema_sha256": "b" * 64,
        "request_monotonic_ns": 100,
        "response_monotonic_ns": 200,
        "pairing_method": "native_request_id",
        "pairing_evidence": ["framework.request_id=response.request_id"],
    }


class ModelInvocationContextTests(unittest.TestCase):
    def test_valid_privacy_preserving_context(self):
        value = context()
        validate_context(value)
        result = validate_contexts([value], "run", {"session"})
        self.assertTrue(result["all_sessions_covered"])
        self.assertNotIn("system_prompt", value)

    def test_rejects_placeholder_hash(self):
        value = context()
        value["system_prompt_sha256"] = "unknown"
        with self.assertRaisesRegex(ValueError, "SHA256"):
            validate_context(value)

    def test_rejects_response_before_request(self):
        value = context()
        value["response_monotonic_ns"] = 99
        with self.assertRaisesRegex(ValueError, "precedes"):
            validate_context(value)

    def test_rejects_duplicate_pair(self):
        value = context()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_contexts([value, copy.deepcopy(value)], "run", {"session"})


if __name__ == "__main__":
    unittest.main()
