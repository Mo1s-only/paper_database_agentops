#!/usr/bin/env python3
"""Freeze actual canary inputs; compare strict process matching and shared-ID matching."""
import argparse
import json
from pathlib import Path

from align_candidates import ROOT, sha256, write_json
from align_application import run as align_run
from normalize_runs import normalize_sqlite


def prepare(run_dir: Path):
    output = run_dir / "alignment-inputs"
    output.mkdir(exist_ok=False)
    db = run_dir / "session.db"
    app = run_dir / "parsed" / "application-events.jsonl"
    scope = json.loads((run_dir / "capture-scope.json").read_text(encoding="utf-8"))
    source = db.resolve().relative_to(ROOT).as_posix()
    # The launcher lives inside a WSL PID namespace; eBPF reports different kernel PIDs.
    # Never copy the launcher's namespace/clock declaration onto AgentSight observations.
    scope.update(source_path=source, source_sha256=sha256(db), pid_namespace=None,
                 clock_domain="agentsight-reconstructed-wall-ms", uncertainty_ms=None,
                 clock_boundary="Observed AgentSight timestamps differ from launcher CLOCK_REALTIME; conversion uncalibrated",
                 pid_boundary="Kernel-side PID namespace mapping to WSL application PIDs is not yet measured")
    write_json(output / "observation-scope.json", scope)
    artifacts = []
    for path, category in [(db, "raw_observation"), (app, "app_log")]:
        artifacts.append({"path": path.resolve().relative_to(ROOT).as_posix(), "category": category,
                          "sha256": sha256(path)})
    write_json(output / "run.json", {"run_id": run_dir.name, "evidence_kind": "runtime_observed", "artifacts": artifacts,
                                     "app_transformation": "parse_claude_native.py; raw refs in parsed/native-event-provenance.jsonl"})
    evidence = output / "evidence-events.jsonl"
    with evidence.open("x", encoding="utf-8") as stream:
        emitted, skipped = normalize_sqlite(db, stream)
    summaries = {}
    for mode in ("process-and-tool", "shared-tool-id", "session-and-tool"):
        summaries[mode] = align_run(output / "run.json", evidence, app, output / "observation-scope.json",
                                    run_dir / ("alignment-" + mode), mode)
    native_tools = [json.loads(line) for line in app.read_text(encoding="utf-8").splitlines()
                    if json.loads(line)["event_type"] == "tool.start"]
    system = [json.loads(line) for line in evidence.read_text(encoding="utf-8").splitlines()]
    system_ids = {r.get("tool_call_id") for r in system if r["record_type"] == "agentsight.tool_calls"}
    missing = [r["tool_call_id"] for r in native_tools if r["tool_call_id"] not in system_ids]
    raw = (run_dir / "raw-stream.log").read_text(encoding="utf-8", errors="replace")
    report = {"run_id": run_dir.name, "normalized_system_records": emitted, "skipped": skipped,
              "native_tool_starts": len(native_tools), "system_tool_ids": len(system_ids),
              "capture_status": "complete" if len(native_tools) == len(system_ids) and not missing else "incomplete",
              "system_edge_claim_allowed": len(native_tools) == len(system_ids) and not missing,
              "missing_ids": [{"tool_call_id": ident, "present_as_text_in_debug_stream": ident in raw} for ident in missing],
              "identity_modes": {mode: s["status_counts"] for mode, s in summaries.items()},
              "scope": "Exact native tool IDs only; no PID translation, clock calibration or responsibility claim",
              "ground_truth_used_for_alignment": False}
    write_json(run_dir / "real-alignment-comparison.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.run), ensure_ascii=False))
