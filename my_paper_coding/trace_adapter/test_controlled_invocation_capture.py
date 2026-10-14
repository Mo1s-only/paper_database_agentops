import unittest
from unittest.mock import patch

from controlled_invocation_capture import prepare_request, finalize_response


class ControlledInvocationCaptureTests(unittest.TestCase):
    def request(self):
        with patch("controlled_invocation_capture.time.monotonic_ns", return_value=100):
            return prepare_request(
                run_id="run", session_id="session", agent_id="agent",
                model_id="provider-model", model_version="2026-10-01",
                temperature=0.0, top_p=1.0, system_prompt="private prompt",
                tool_schema={"b": 2, "a": 1})

    def test_prepare_hashes_content_without_storing_it(self):
        value = self.request()
        self.assertNotIn("system_prompt", value)
        self.assertNotIn("tool_schema", value)
        self.assertEqual(len(value["system_prompt_sha256"]), 64)
        self.assertEqual(value["request_monotonic_ns"], 100)

    def test_tool_schema_hash_is_key_order_independent(self):
        first = self.request()
        with patch("controlled_invocation_capture.time.monotonic_ns", return_value=100):
            second = prepare_request(
                run_id="run", session_id="session", agent_id="agent",
                model_id="provider-model", model_version="2026-10-01",
                temperature=0.0, top_p=1.0, system_prompt="private prompt",
                tool_schema={"a": 1, "b": 2})
        self.assertEqual(first["tool_schema_sha256"], second["tool_schema_sha256"])

    def test_finalize_binds_native_response(self):
        value = finalize_response(self.request(), "resp-native", 200)
        self.assertEqual(value["response_id"], "resp-native")
        self.assertEqual(value["response_monotonic_ns"], 200)

    def test_finalize_rejects_response_before_request(self):
        with self.assertRaisesRegex(ValueError, "precedes"):
            finalize_response(self.request(), "resp-native", 99)

    def test_prepare_rejects_unbounded_sampling_parameter(self):
        with self.assertRaisesRegex(ValueError, "top_p"):
            prepare_request(
                run_id="run", session_id="session", agent_id="agent",
                model_id="provider-model", model_version="2026-10-01",
                temperature=0.0, top_p=1.1, system_prompt="prompt",
                tool_schema={})


if __name__ == "__main__":
    unittest.main()
