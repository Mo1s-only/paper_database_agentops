#!/usr/bin/env python3
"""Replay one label-isolated public-dataset task under Claude, AgentSight and eBPF."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import socket
import sqlite3
import subprocess
import time
import zipfile

from capture_real_application import capture_agent, save, stop
from claude_tool_id_bridge_hook import KNOWN_SCENARIO_SCRIPTS
from analyze_scenario_tool_id_bridge import analyze
from parse_claude_native import convert
from prepare_real_alignment import prepare as prepare_alignment


ROOT = Path(__file__).resolve().parents[2]
DATASETS = ROOT / "Reference paper" / "datasets"
DEFAULT_BASE = ROOT / "lab" / "experiment" / "public_dataset_cross_layer_20261022"
USD_CNY_PLANNING_RATE = 10.0
DEFAULT_SESSION_SOFT_CAP_USD = 0.025
DEFAULT_INCREMENTAL_CAP_CNY = 1.0
SELECTION = {
    "AgentTrace": {
        "sample_id": "cod_034b23",
        "path": "shared_data/AgentTrace_ICLR2026_data/traces/cod_034b23_trace.json",
    },
    "WhoAndWhen": {
        "sample_id": "99da66d8af02491f98b98c56b26c709e773b5a2ad945fb280375951ba600de09",
        "path": "shared_data/WhoAndWhen_184/Algorithm-Generated/99.json",
    },
    "TRAIL": {
        "sample_id": "0035f455b3ff2295167a844f04d85d34",
        "annotation": "benchmarking/processed_annotations_gaia/0035f455b3ff2295167a844f04d85d34.json",
        "trace": "benchmarking/data/GAIA/0035f455b3ff2295167a844f04d85d34.json",
        "path": "shared_data/TRAIL_benchmarking_148_traces.zip",
    },
}


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def flatten_spans(trace: dict) -> list[dict]:
    pending = list(trace.get("spans", []))
    result = []
    while pending:
        span = pending.pop()
        result.append(span)
        pending.extend(span.get("child_spans", []))
    return result


def public_input(dataset: str, sample_id: str) -> tuple[dict, dict]:
    if dataset not in SELECTION or sample_id != SELECTION[dataset]["sample_id"]:
        raise ValueError("Only the preselected, pinned dataset sample is allowed")
    spec = SELECTION[dataset]
    source_path = (DATASETS / spec["path"]).resolve()
    if not source_path.is_relative_to(DATASETS.resolve()) or not source_path.is_file():
        raise ValueError("Pinned public dataset source is missing or outside its allowed root")
    source_bytes = source_path.read_bytes()
    if dataset == "AgentTrace":
        raw = json.loads(source_bytes)
        trace = json.loads(raw["trace_json"])
        nodes = []
        for node in trace.get("nodes", []):
            data = {key: value for key, value in node.get("data", {}).items()
                    if key not in {"is_bug_point", "bug_description", "content"}}
            metadata = {key: value for key, value in node.get("metadata", {}).items()
                        if key not in {"bug_type", "root_cause", "error_label"}}
            nodes.append({key: node.get(key) for key in ("id", "type", "agent_id", "timestamp", "parent_ids")}
                         | {"data": data, "metadata": metadata})
        value = {"dataset": dataset, "sample_id": sample_id,
                 "task": "Summarize the anonymized multi-agent execution graph structure.",
                 "graph": {"run_id": trace.get("run_id"), "nodes": nodes,
                           "edges": trace.get("edges", [])}}
        record_hash = digest(source_bytes)
    elif dataset == "WhoAndWhen":
        raw = json.loads(source_bytes)
        history = [{"role": row.get("role", "unknown"),
                    "content": str(row.get("content", ""))[:4000]}
                   for row in raw.get("history", [])[:8]]
        value = {"dataset": dataset, "sample_id": sample_id,
                 "task": str(raw.get("question", ""))[:2000],
                 "level": raw.get("level"), "history": history}
        record_hash = digest(source_bytes)
    else:
        with zipfile.ZipFile(source_path) as archive:
            annotation_bytes = archive.read(spec["annotation"])
            trace_bytes = archive.read(spec["trace"])
        trace = json.loads(trace_bytes)
        spans = [{"span_id": span.get("span_id"), "parent_span_id": span.get("parent_span_id"),
                  "span_name": span.get("span_name"), "span_kind": span.get("span_kind"),
                  "timestamp": span.get("timestamp"), "duration": span.get("duration"),
                  "service_name": span.get("service_name"),
                  "attribute_keys": sorted((span.get("span_attributes") or {}).keys())}
                 for span in flatten_spans(trace)]
        value = {"dataset": dataset, "sample_id": sample_id,
                 "task": "Summarize the historical trace topology and operation types; do not infer error labels.",
                 "trace_id": trace.get("trace_id"), "spans": spans}
        record_hash = digest(annotation_bytes)
    # Gold labels, answer fields, and error descriptions never enter the runtime task input.
    return value, {"dataset": dataset, "sample_id": sample_id,
                   "source_path": spec["path"], "source_sha256": digest(source_bytes),
                   "selected_record_sha256": record_hash,
                   "historical_annotation_used_as_runtime_input": False}


def safe_table_counts(db: Path) -> dict:
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as connection:
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        counts = {name: connection.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
                  for name in ("llm_calls", "tool_calls", "token_usage", "process_nodes", "audit_events")
                  if name in tables}
        process_events = 0
        if "audit_events" in tables:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(audit_events)")}
            if "audit_type" in columns:
                process_events = connection.execute(
                    "SELECT count(*) FROM audit_events WHERE audit_type='process'").fetchone()[0]
    return {"counts": counts, "process_audit_events": process_events,
            "ebpf_system_capture_present": counts.get("process_nodes", 0) > 0 and process_events > 0,
            "agentsight_tool_semantics_present": counts.get("tool_calls", 0) > 0,
            "llm_semantics_present": counts.get("llm_calls", 0) > 0}


def prior_reported_cost(output_parent: Path) -> float:
    total = 0.0
    if not output_parent.exists():
        return total
    for run_dir in output_parent.iterdir():
        if not run_dir.is_dir() or not (run_dir / "plan.json").exists():
            continue
        summary_path = run_dir / "capture-summary.json"
        if not summary_path.is_file():
            raise ValueError(f"Refusing to proceed with unresolved prior run: {run_dir.name}")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("real_api") is not True or summary.get("cost_complete") is not True:
            raise ValueError(f"Refusing to proceed with unresolved prior run: {summary_path.parent.name}")
        cost = summary.get("reported_cost_usd")
        if cost is None or float(cost) < 0:
            raise ValueError(f"Prior run has no verified CLI cost: {summary_path.parent.name}")
        total += float(cost)
    return total


def finalize(output: Path, dataset: str, sample_id: str, provenance: dict,
             prior_cost: float, incremental_cap_cny: float, result: dict) -> dict:
    cost = result.get("reported_cost_usd")
    if cost is None:
        raise RuntimeError("Claude CLI did not report a cost; incremental budget cannot be verified")
    actual_cny = (prior_cost + float(cost)) * USD_CNY_PLANNING_RATE
    cost_status = "within_incremental_cap" if actual_cny <= incremental_cap_cny else "exceeded_incremental_cap"
    counts = safe_table_counts(output / "session.db")
    parsed_output = output / "parsed"
    if parsed_output.exists() and parsed_output.is_dir() and not any(parsed_output.iterdir()):
        parsed_output.rmdir()
    parser_report = convert(output, parsed_output, ("agent_a",))
    alignment = prepare_alignment(output, "alignment-inputs")
    audit = analyze(output)
    controlled = json.loads((output / "alignment-inputs" / "controlled-instrumentation" /
                             "controlled-instrumentation-report.json").read_text(encoding="utf-8"))
    save(output / "capture-summary.json", {
        "real_api": True, "api_sessions": 1, "automatic_retries": 0,
        "dataset": dataset, "sample_id": sample_id,
        "reported_cost_usd": float(cost), "reported_cost_cny_at_planning_rate": float(cost) * USD_CNY_PLANNING_RATE,
        "prior_incremental_cli_cost_usd": prior_cost,
        "projected_incremental_total_cny": actual_cny,
        "incremental_cap_cny": incremental_cap_cny,
        "cost_complete": True, "cost_status": cost_status,
        "agent": {key: result[key] for key in ("agent_id", "session_id", "pid", "exit_code", "success", "stream_lines")},
        "dataset_input": {key: provenance[key] for key in
                          ("source_sha256", "selected_record_sha256", "task_input_sha256")},
        "capture": counts, "native_parser": parser_report,
        "alignment": {"native_tool_starts": alignment["native_tool_starts"],
                      "agentsight_tool_ids": alignment["system_tool_ids"],
                      "session_and_tool": alignment["identity_modes"].get("session-and-tool"),
                      "capture_status": alignment["capture_status"]},
        "controlled_instrumentation": {
            "native_tool_starts": controlled["native_tool_starts"],
            "accepted_tool_to_ebpf_process_lineage": controlled["claims"]["direct_hook_id_to_ebpf_lineage"],
            "relation_status_counts": controlled["status_counts"],
            "passive_agentsight_identity": False},
        "tool_id_process_audit": {
            "native_tools": audit["native_tool_count"],
            "exact_native_agentsight_tool_id_matches": audit["exact_native_agentsight_tool_id_matches"],
            "ebpf_exec_events": audit["ebpf_exec_event_count"]},
        "success_gate": {
            "api_session_success": bool(result["success"]),
            "agent_semantics_present": parser_report["native_provenance_complete"],
            "agentsight_llm_and_tool_semantics_present": counts["llm_semantics_present"] and counts["agentsight_tool_semantics_present"],
            "ebpf_system_data_present": counts["ebpf_system_capture_present"],
            "session_tool_link_complete": alignment["capture_status"] == "complete",
            "controlled_tool_id_to_ebpf_lineage_complete": controlled["claims"]["direct_hook_id_to_ebpf_lineage"] == controlled["native_tool_starts"] and controlled["native_tool_starts"] > 0,
            "within_user_incremental_cap": cost_status == "within_incremental_cap"},
        "claim_boundary": "This proves only a dataset-derived task replay and this capture/alignment path; controlled hook ID injection is explicit instrumentation, not passive AgentSight behavior; no responsibility or causal accuracy is claimed.",
    })
    return json.loads((output / "capture-summary.json").read_text(encoding="utf-8"))


def capture(args: argparse.Namespace) -> dict:
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite run: {output}")
    if not 0 < args.per_session_budget <= DEFAULT_SESSION_SOFT_CAP_USD:
        raise ValueError("CLI session soft ceiling must be in (0, 0.025] USD")
    if args.incremental_cap_cny != DEFAULT_INCREMENTAL_CAP_CNY:
        raise ValueError("This batch is pinned to the user-authorized 1 CNY incremental cap")
    if os.geteuid() != 0:
        raise RuntimeError("Ubuntu WSL root is required for AgentSight/eBPF")
    if not (os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")):
        raise RuntimeError("No API credential is configured in the process environment")
    from urllib.parse import urlparse
    endpoint = urlparse(os.environ.get("ANTHROPIC_BASE_URL", ""))
    if (endpoint.scheme, endpoint.hostname, endpoint.path.rstrip("/")) != (
            "https", "api.deepseek.com", "/anthropic"):
        raise RuntimeError("Unexpected API endpoint; only the configured DeepSeek Anthropic route is permitted")
    socket.getaddrinfo(endpoint.hostname, 443)
    if not Path("/sys/kernel/tracing/events/sched/sched_process_exec").exists():
        subprocess.run(["mount", "-t", "tracefs", "tracefs", "/sys/kernel/tracing"], check=True)
    prior_cost = prior_reported_cost(output.parent)
    projected_cny = (prior_cost + args.per_session_budget) * USD_CNY_PLANNING_RATE
    if projected_cny > args.incremental_cap_cny + 1e-9:
        raise RuntimeError("The 1 CNY incremental batch ceiling would be exceeded; no API request sent")

    task_input, provenance = public_input(args.dataset, args.sample_id)
    output.mkdir(parents=True)
    workspace = output / "workspace"
    workspace.mkdir()
    input_path = workspace / "public-input.json"
    save(input_path, task_input)
    provenance["task_input_sha256"] = digest(input_path.read_bytes())
    save(output / "dataset-provenance.json", provenance)
    scope = {"schema_version": "agentops-observation-scope-v0.1", "run_id": output.name,
             "evidence_kind": "runtime_observed",
             "host_id": hashlib.sha256(Path("/etc/machine-id").read_bytes()).hexdigest(),
             "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
             "pid_namespace": os.readlink("/proc/self/ns/pid"), "clock_domain": "linux-CLOCK_REALTIME-ms",
             "uncertainty_ms": 1, "clock_boundary": "Same Linux kernel wall clock; 1ms quantization bound"}
    save(output / "capture-scope.json", scope)
    tools_script = Path(__file__).with_name("public_dataset_runtime_probe.py").resolve()
    if tools_script.name not in KNOWN_SCENARIO_SCRIPTS:
        raise RuntimeError("Dataset replay probe is not allowlisted for controlled hook instrumentation")
    prompt = (
        f"Dataset-derived replay case: {args.dataset} / {args.sample_id}. "
        "The input JSON is label-isolated and contains no gold attribution fields. "
        "Use Bash exactly once to run this command: python3 " + shlex.quote(str(tools_script)) +
        " --input " + shlex.quote(str(input_path)) +
        ". Read its JSON output and report only dataset, sample_id, and item_count. Do not use another tool."
    )
    save(output / "plan.json", {
        "run_id": output.name, "dataset": args.dataset, "sample_id": args.sample_id,
        "task_input_contains_gold_labels": False,
        "api_provider": "deepseek", "model": os.environ.get("ANTHROPIC_MODEL", "unknown"),
        "sessions": 1, "session_cli_soft_cap_usd": args.per_session_budget,
        "incremental_cap_cny": args.incremental_cap_cny,
        "planning_fx_cny_per_usd": USD_CNY_PLANNING_RATE,
        "prior_incremental_cli_cost_usd": round(prior_cost, 8),
        "projected_incremental_cny": round(projected_cny, 6),
        "historic_cumulative_invoice_reconciled": False,
        "tool_id_bridge": {"enabled": True, "mode": "controlled_hook_instrumentation",
                           "not_passive_agentsight": True},
        "no_automatic_retry": True,
        "validation_scope": "Dataset-derived task replay and runtime layer capture; not original dataset re-execution or attribution accuracy",
    })
    versions = {name: subprocess.run([binary, "--version"], capture_output=True, text=True).stdout.strip()
                for name, binary in (("claude", "claude"), ("agentsight", args.agentsight_bin),
                                     ("python3", "python3"))}
    binary_path = Path(args.agentsight_bin).resolve(strict=True)
    versions["agentsight_sha256"] = digest(binary_path.read_bytes())
    save(output / "versions.json", versions)
    os.environ["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    db = output / "session.db"
    record_log = (output / "record.log").open("x", encoding="utf-8")
    raw_log = (output / "raw-stream.log").open("x", encoding="utf-8")
    lifecycle = output / "observer-lifecycle.jsonl"
    observer = debug = None

    def marker(stage: str, **extra):
        row = {"stage": stage, "wall_time_ns": time.time_ns(), "monotonic_ns": time.monotonic_ns(),
               "observer_pid": observer.pid if observer else None,
               "debug_pid": debug.pid if debug else None,
               "observer_exit_code": observer.poll() if observer else None,
               "debug_exit_code": debug.poll() if debug else None, **extra}
        with lifecycle.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    result = None
    try:
        observer = subprocess.Popen([args.agentsight_bin, "record", "-c", "claude", "--db", str(db), "--no-server"],
                                    cwd=output, stdout=record_log, stderr=subprocess.STDOUT,
                                    start_new_session=True)
        time.sleep(2)
        if observer.poll() is not None:
            raise RuntimeError("AgentSight recorder exited before replay")
        debug = subprocess.Popen([args.agentsight_bin, "debug", "process"], cwd=output,
                                 stdout=raw_log, stderr=subprocess.STDOUT, start_new_session=True)
        time.sleep(1)
        if debug.poll() is not None:
            raise RuntimeError("AgentSight eBPF process observer exited before replay")
        marker("capture_ready")
        hook_events = output / "agent_a-tool-call-hook-events.jsonl"
        marker("agent_a_start")
        result = capture_agent(output, "agent_a", prompt, "Bash", args.per_session_budget,
                               scope, tool_id_bridge_events=hook_events,
                               allow_known_scenario_scripts=True)
        marker("agent_a_finished", success=result["success"],
               reported_cost_usd=result["reported_cost_usd"], stream_lines=result["stream_lines"])
        time.sleep(1)
    finally:
        marker("stop_requested")
        if observer is not None:
            stop(observer)
        if debug is not None:
            stop(debug)
        marker("stopped")
        record_log.close()
        raw_log.close()

    if result is None:
        raise RuntimeError("No Claude result was captured; automatic retry is disabled")
    return finalize(output, args.dataset, args.sample_id, provenance, prior_cost,
                    args.incremental_cap_cny, result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=tuple(SELECTION), required=True)
    parser.add_argument("--sample-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--agentsight-bin", required=True)
    parser.add_argument("--per-session-budget", type=float, default=DEFAULT_SESSION_SOFT_CAP_USD)
    parser.add_argument("--incremental-cap-cny", type=float, default=DEFAULT_INCREMENTAL_CAP_CNY)
    parser.add_argument("--finalize-existing", action="store_true",
                        help="Build adapter reports from an already captured run without issuing an API request")
    args = parser.parse_args()
    try:
        if args.finalize_existing:
            output = args.output.resolve()
            if not output.is_dir() or (output / "capture-summary.json").exists():
                raise ValueError("Finalize mode requires an existing incomplete run directory")
            plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
            provenance = json.loads((output / "dataset-provenance.json").read_text(encoding="utf-8"))
            result = json.loads((output / "agent_a-capture-summary.json").read_text(encoding="utf-8"))
            report = finalize(output, args.dataset, args.sample_id, provenance,
                              float(plan["prior_incremental_cli_cost_usd"]),
                              args.incremental_cap_cny, result)
        else:
            report = capture(args)
    except Exception as exc:
        request_sent = (args.output / "claude-agent-a.log").exists()
        print(json.dumps({"status": "failed_or_blocked", "exception_type": type(exc).__name__,
                          "api_request_sent": request_sent,
                          "run_artifact_directory": str(args.output)}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False))
    gate = report["success_gate"]
    required = ("api_session_success", "agent_semantics_present", "agentsight_llm_and_tool_semantics_present",
                "ebpf_system_data_present", "session_tool_link_complete",
                "controlled_tool_id_to_ebpf_lineage_complete", "within_user_incremental_cap")
    return 0 if all(gate[name] for name in required) else 3


if __name__ == "__main__":
    raise SystemExit(main())
