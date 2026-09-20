#!/usr/bin/env python3
"""Offline regression test for the AgentSight-to-Watson reproduction chain."""
import json
import sqlite3
import tempfile
from pathlib import Path

from watson import Call, extract_calls, reconstruct, write_jsonl, read_jsonl


class FakeClient:
    def complete(self, prompt, model, temperature, top_p):
        if "Return only YES or NO" in prompt:
            return "YES"
        if "Summarize the following" in prompt:
            return "A constrained explanation was accepted; it is not hidden CoT."
        assert "OBSERVED ANSWER:" not in prompt
        return "Arithmetic supports the result.\nFINAL: " + ("4" if "2+2" in prompt else "unknown")


def main():
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "session.db"
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE llm_calls (id TEXT, start_timestamp_ms INTEGER, model TEXT, provider TEXT, request_body_json TEXT, response_body_json TEXT)")
        request = {"system": "Be concise.", "messages": [{"role": "user", "content": "What is 2+2?"}]}
        response = {"text_content": "4"}
        con.execute("INSERT INTO llm_calls VALUES (?, ?, ?, ?, ?, ?)", ("c1", 1, "mirror-model", "test", json.dumps(request), json.dumps(response)))
        con.commit(); con.close()
        calls = extract_calls(db)
        assert len(calls) == 1 and calls[0].prompt and calls[0].output == "4"
        manifest = Path(directory) / "calls.jsonl"; write_jsonl(manifest, calls)
        restored = read_jsonl(manifest); assert restored[0].id == "c1"
        report = reconstruct(restored[0], FakeClient(), "mirror-model", 2, 0.0, 1.0)
        assert report["status"] == "complete" and report["accepted"] == 2
    print("PASS: AgentSight extraction and Watson RepCoT offline pipeline")


if __name__ == "__main__":
    main()

