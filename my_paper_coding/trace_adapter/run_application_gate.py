#!/usr/bin/env python3
"""Persist a synthetic two-agent protocol gate. No API, subprocess agent or eBPF capture."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sqlite3

from align_candidates import ROOT, sha256, write_json, write_jsonl
from align_application import join_application, run
from application_events import EventWriter, read_events
from normalize_runs import normalize_sqlite


def fixture_events():
    from application_events import VERSION
    events = []
    for label, proc in (("a", 101), ("b", 202)):
        for index, kind in enumerate(("session.start", "step.start", "tool.start", "tool.end", "step.end", "session.end")):
            events.append({"schema_version": VERSION, "evidence_kind": "synthetic_fixture", "run_id": "app-protocol-fixture",
                           "event_id": f"event-{label}-{index}", "session_id": f"session-{label}", "agent_id": f"agent_{label}",
                           "event_type": kind, "sequence": index, "timestamp_ms": 1100 + index * 10,
                           "step_id": None if kind.startswith("session.") else f"step-{label}",
                           "tool_call_id": f"call-{label}" if kind.startswith("tool.") else None,
                           "process": {"host_id": "fixture-host", "boot_id": "fixture-boot", "pid_namespace": "fixture-ns",
                                       "pid": proc, "start_ms": 1000},
                           "clock": {"domain": "fixture-clock", "uncertainty_ms": 1}})
    return events


def fixture_scope(source_path="fixture.db", digest="fixture"):
    return {"schema_version": "agentops-observation-scope-v0.1", "run_id": "app-protocol-fixture",
            "evidence_kind": "synthetic_fixture", "source_path": source_path, "source_sha256": digest,
            "host_id": "fixture-host", "boot_id": "fixture-boot", "pid_namespace": "fixture-ns",
            "clock_domain": "fixture-clock", "uncertainty_ms": 1}


def fixture_records(path="fixture.db"):
    records = []
    for label, proc in (("a", 101), ("b", 202)):
        for table, fields in (("process_nodes", {"id": f"process-{label}", "pid": proc, "start_timestamp_ms": 1000, "end_timestamp_ms": 2000}),
                              ("tool_calls", {"id": f"tool-{label}", "related_pid": proc, "tool_call_id": f"call-{label}", "start_timestamp_ms": 1115})):
            records.append({"record_type": "agentsight." + table, "evidence_status": "observed",
                            "event_id": fields["id"], "pid": fields.get("pid"), "timestamp": fields["start_timestamp_ms"],
                            "tool_call_id": fields.get("tool_call_id"), "fields": fields,
                            "source": {"path": path, "table": table, "row": fields["id"], "role": "raw_observation"}})
    return records


def scenarios(events, records, scope):
    """Expected statuses are protocol/robustness assertions, not empirical accuracy labels."""
    cases = []

    def record(rows, name):
        return next(r for r in rows if r["source"]["row"] == name)

    def add(name, expected, edit):
        app, system, metadata = copy.deepcopy((events, records, scope))
        edit(app, system, metadata)
        try:
            decisions, summary = join_application(app, system, metadata, "synthetic-app-events.jsonl")
            actual = [d["status"] for d in decisions]
            reasons = [d["reason"] for d in decisions]
        except ValueError as error:
            actual, reasons = "invalid_stream", [str(error)]
        cases.append({"name": name, "expected": expected, "actual": actual, "passed": actual == expected,
                      "reasons": reasons, "evidence_kind": "synthetic_fixture"})

    add("baseline", ["accepted", "accepted"], lambda a, r, s: None)
    def remove_id(a, r, s):
        record(r, "tool-a")["tool_call_id"] = None
        record(r, "tool-a")["fields"]["tool_call_id"] = None
    add("missing_system_tool_id", ["abstain", "accepted"], remove_id)
    def duplicate_tool(a, r, s):
        other = copy.deepcopy(record(r, "tool-a")); other["source"]["row"] = "duplicate-tool"; r.append(other)
    add("duplicate_system_tool_id", ["uncertain", "accepted"], duplicate_tool)
    add("tool_pid_conflict", ["uncertain", "accepted"], lambda a, r, s: record(r, "tool-a")["fields"].update(related_pid=999))
    add("different_run", ["abstain", "abstain"], lambda a, r, s: s.update(run_id="another-run"))
    add("different_host", ["abstain", "abstain"], lambda a, r, s: s.update(host_id="another-host"))
    add("different_boot", ["abstain", "abstain"], lambda a, r, s: s.update(boot_id="another-boot"))
    add("different_pid_namespace", ["abstain", "abstain"], lambda a, r, s: s.update(pid_namespace="another-ns"))
    add("different_clock", ["abstain", "abstain"], lambda a, r, s: s.update(clock_domain="another-clock"))
    add("unbounded_clock", ["abstain", "abstain"], lambda a, r, s: s.update(uncertainty_ms=None))
    add("clock_interval_crosses_lifetime", ["uncertain", "uncertain"], lambda a, r, s: s.update(uncertainty_ms=500))
    add("reused_pid_different_start", ["abstain", "accepted"], lambda a, r, s: record(r, "process-a")["fields"].update(start_timestamp_ms=900))
    def unknown_competitor(a, r, s):
        other = copy.deepcopy(record(r, "process-a")); other["source"]["row"] = "unknown-process"
        other["fields"]["start_timestamp_ms"] = None; r.append(other)
    add("unknown_process_competitor", ["uncertain", "accepted"], unknown_competitor)
    def multiple_owners(a, r, s):
        extra = copy.deepcopy(a[:6])
        for e in extra:
            e["session_id"] = "session-other"; e["agent_id"] = "agent_other"; e["event_id"] += "-other"
        a.extend(extra)
    add("multiple_application_owners", ["uncertain", "accepted", "uncertain"], multiple_owners)
    add("truncated_stream", "invalid_stream", lambda a, r, s: a.pop())
    add("tool_end_without_start", "invalid_stream", lambda a, r, s: a[2].update(event_type="tool.end"))
    add("agent_identity_changes", "invalid_stream", lambda a, r, s: a[3].update(agent_id="changed"))
    add("sequence_gap", "invalid_stream", lambda a, r, s: a[3].update(sequence=12))
    add("boolean_timestamp", "invalid_stream", lambda a, r, s: a[3].update(timestamp_ms=True))
    add("mixed_evidence_kind", "invalid_stream", lambda a, r, s: a[3].update(evidence_kind="runtime_observed"))
    return cases


def run_gate(output: Path):
    if output.exists():
        raise FileExistsError("Gate output already exists")
    output.resolve().relative_to(ROOT)  # Keep locators rooted in this repository.
    output.mkdir(parents=True)
    db = output / "synthetic-session.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE process_nodes(id TEXT PRIMARY KEY, pid INTEGER, start_timestamp_ms INTEGER, end_timestamp_ms INTEGER)")
        conn.execute("CREATE TABLE tool_calls(id TEXT PRIMARY KEY, related_pid INTEGER, tool_call_id TEXT, start_timestamp_ms INTEGER)")
        conn.executemany("INSERT INTO process_nodes VALUES(?,?,?,?)", [("process-a", 101, 1000, 2000), ("process-b", 202, 1000, 2000)])
        conn.executemany("INSERT INTO tool_calls VALUES(?,?,?,?)", [("tool-a", 101, "call-a", 1115), ("tool-b", 202, "call-b", 1115)])
    events = fixture_events()
    # Exercise the writer lifecycle, then retain emitted UUIDs as actual fixture event IDs.
    all_events = []
    for label, session_events in (("a", events[:6]), ("b", events[6:])):
        head = session_events[0]
        writer = EventWriter(output / f"synthetic-agent-{label}.jsonl", head["run_id"], head["session_id"], head["agent_id"],
                             head["process"], head["clock"], "synthetic_fixture")
        try:
            for e in session_events:
                writer.emit(e["event_type"], e["step_id"], e["tool_call_id"], e["timestamp_ms"])
            writer.finish()
        finally:
            writer.close()
        written, _ = read_events(writer.path)
        all_events.extend(written)
    app = output / "synthetic-application-events.jsonl"
    write_jsonl(app, all_events)
    evidence = output / "evidence-events.jsonl"
    with evidence.open("x", encoding="utf-8") as stream:
        normalize_sqlite(db, stream)
    manifest = output / "run.json"
    write_json(manifest, {"run_id": "app-protocol-fixture", "evidence_kind": "synthetic_fixture", "artifacts": [
        {"path": p.resolve().relative_to(ROOT).as_posix(), "category": category, "sha256": sha256(p)}
        for p, category in ((db, "raw_observation"), (app, "app_log"))]})
    scope_path = output / "observation-scope.json"
    scope = fixture_scope(db.resolve().relative_to(ROOT).as_posix(), sha256(db))
    write_json(scope_path, scope)
    result = run(manifest, evidence, app, scope_path, output / "baseline-alignment")
    records = [json.loads(line) for line in evidence.read_text(encoding="utf-8").splitlines()]
    cases = scenarios(all_events, records, scope)
    report = {"evidence_kind": "synthetic_fixture", "real_model_calls": 0, "real_agentsight_captures": 0,
              "cases": cases, "passed": sum(c["passed"] for c in cases), "total": len(cases),
              "baseline_tool_identity_gate_passed": result["tool_identity_gate_passed"],
              "baseline_application_events": len(all_events), "baseline_system_records": len(records),
              "code_sha256": {name: sha256(Path(__file__).with_name(name)) for name in
                              ("application_events.py", "align_application.py", "run_application_gate.py")},
              "precision": None, "recall": None, "boundary": "Controlled protocol assertions, not real attribution accuracy"}
    write_json(output / "protocol-gate-report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_gate(args.output)
    print(json.dumps({k: result[k] for k in ("passed", "total", "baseline_tool_identity_gate_passed", "real_model_calls")}))
    raise SystemExit(0 if result["passed"] == result["total"] else 2)
