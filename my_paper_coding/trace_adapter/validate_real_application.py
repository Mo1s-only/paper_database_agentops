#!/usr/bin/env python3
"""Audit a real run against native tool IDs and the controlled task requirement."""
import argparse
import json
from pathlib import Path
import sqlite3

from align_candidates import sha256, write_json


def validate(run: Path, alignment_name="alignment-shared-tool-id"):
    native, response_ids, stdout = {}, {}, None
    for agent in ("a", "b"):
        response_ids[agent] = set()
        for line, raw in enumerate((run / f"claude-agent-{agent}.log").read_text(encoding="utf-8").splitlines(), 1):
            item = json.loads(raw)
            message = item.get("message", {})
            if item.get("type") == "assistant":
                if message.get("id"):
                    response_ids[agent].add(message["id"])
                for block in message.get("content", []):
                    if block.get("type") == "tool_use":
                        native[block["id"]] = {"agent": "agent_" + agent, "name": block["name"], "raw_line": line}
            tool_result = item.get("tool_use_result")
            if isinstance(tool_result, dict) and "stdout" in tool_result:
                stdout = json.loads(tool_result["stdout"])
    route = json.loads((run / "workspace/route.json").read_text(encoding="utf-8"))
    decision = json.loads((run / "workspace/decision.json").read_text(encoding="utf-8"))
    pairs = []
    db = run / "session.db"
    with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        for text in (run / alignment_name / "application-alignments.jsonl").read_text(encoding="utf-8").splitlines():
            prediction = json.loads(text)
            if prediction["status"] != "accepted":
                continue
            ident = prediction["tool_call_id"]
            row = connection.execute("SELECT * FROM tool_calls WHERE tool_call_id=?", (ident,)).fetchall()
            pairs.append({"tool_call_id": ident, "native_agent": native[ident]["agent"], "tool_name": native[ident]["name"],
                          "native_line": native[ident]["raw_line"], "single_system_tool_row": len(row) == 1,
                          "agent_matches_native": prediction["agent_id"] == native[ident]["agent"],
                          "system_pid": row[0]["related_pid"] if row else None,
                          "scope": "shared-key consistency, not independent semantic ground truth"})
    result = {"run_id": run.name, "alignment_name": alignment_name, "real_cli_sessions": 2,
              "unique_native_assistant_message_ids": {k: len(v) for k, v in response_ids.items()},
              "model_call_count_boundary": "Native response message IDs are not a network-request/retry audit",
              "native_tool_calls": native, "accepted_key_audit": pairs,
              "task_validation": {"route_requires_one": route.get("required_available") == 1,
                  "actual_tool_reported_zero": bool(stdout) and (stdout.get("available", stdout.get("observed_available")) == 0),
                  "decision_matches_actual_tool": bool(stdout) and decision.get("observed_available") == stdout.get("available", stdout.get("observed_available")),
                  "task_requirement_satisfied": decision.get("satisfied"),
                  "scope": "controlled inventory tool; correct failure recognition is not attribution accuracy"},
              "source_sha256": {p.name: sha256(p) for p in [db, run / "claude-agent-a.log", run / "claude-agent-b.log"]},
              "code_sha256": {name: sha256(Path(__file__).with_name(name)) for name in
                              ("capture_real_application.py", "parse_claude_native.py", "prepare_real_alignment.py", "align_application.py")}}
    assert pairs and all(p["single_system_tool_row"] and p["agent_matches_native"] for p in pairs)
    assert all(result["task_validation"][k] for k in ("route_requires_one", "actual_tool_reported_zero", "decision_matches_actual_tool"))
    assert result["task_validation"]["task_requirement_satisfied"] is False
    output = run / ("real-validation.json" if alignment_name == "alignment-shared-tool-id" else f"real-validation-{alignment_name}.json")
    if output.exists():
        raise FileExistsError("Refusing to overwrite validation")
    write_json(output, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--alignment-name", default="alignment-shared-tool-id")
    args = parser.parse_args()
    report = validate(args.run, args.alignment_name)
    print(json.dumps({"matched_tool_ids_checked": len(report["accepted_key_audit"]),
                      "native_response_ids": report["unique_native_assistant_message_ids"],
                      "task_validation": report["task_validation"]}))
