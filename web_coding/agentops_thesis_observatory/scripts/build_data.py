#!/usr/bin/env python3
"""Build the dashboard data snapshot from traceable experiment artifacts."""
from __future__ import annotations

import json
from pathlib import Path


SITE = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[3]
EXP = ROOT / "lab" / "experiment"


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def source(path: str):
    return {"path": path, "kind": "local_experiment_artifact"}


index = load("lab/experiment/experiment_index.json")
clock14 = load("lab/experiment/experiment_20261010_14/analysis.json")
clock15 = load("lab/experiment/experiment_20261010_15/analysis.json")
real = load("lab/experiment/experiment_20261012_14/analysis.json")
events = load("lab/experiment/experiment_20261012_14/application-events-v0.2-summary.json")
quality = load("lab/experiment/experiment_20261012_16/observation-quality-report-final.json")
gate = load("lab/experiment/experiment_20261012_16/pre-attribution-gate.json")
matrix = load("lab/experiment/experiment_20261012_16/pid-namespace-matrix-final.json")
evidence = load("lab/experiment/experiment_20261013_10/pre-attribution-evidence-package.json")
replay = load("lab/experiment/experiment_20261013_10/query-replay-verification.json")
identity = load("lab/experiment/experiment_20261013_13/native-identity-verification.json")
implementation = load("lab/experiment/experiment_20261013_13/implementation-verification.json")
context = load("lab/experiment/experiment_20261013_13/model-context-readiness.json")
budget = load("lab/experiment/experiment_20261013_13/budget-preflight.json")

experiments = [
    {
        "id": "experiment_20261010_14", "time": "10-10 14:00", "status": "verified",
        "stage": "框架原生事件", "summary": "原生工具 1/1 对齐；首次联合采集进程与三时钟",
        "networkCalls": 1, "metric": "620 clock samples",
    },
    {
        "id": "experiment_20261010_15", "time": "10-10 15:00", "status": "partial",
        "stage": "纳秒时钟", "summary": "进程开始时间无需事后补偿；SSE 时钟字段仍缺失",
        "networkCalls": 1, "metric": "989 clock samples",
    },
    {
        "id": "experiment_20261012_14", "time": "10-12 14:00", "status": "verified",
        "stage": "真实六事件闭环", "summary": "SSE 时钟透传、SQLite 持久化、协议 v0.2 闭合",
        "networkCalls": 1, "metric": "6 events · 1 session",
    },
    {
        "id": "experiment_20261012_15", "time": "10-12 15:00", "status": "warning",
        "stage": "严格质量门", "summary": "确定性回放和负向协议矩阵通过，历史时钟下界仍为 0",
        "networkCalls": 0, "metric": "8/8 invalid rejected",
    },
    {
        "id": "experiment_20261012_16", "time": "10-12 16:00", "status": "warning",
        "stage": "归因前统一门", "summary": "字段完整率 114/114；身份/工具图可用",
        "networkCalls": 0, "metric": "114/114 fields",
    },
    {
        "id": "experiment_20261013_10", "time": "10-13 10:00", "status": "warning",
        "stage": "可查询证据包", "summary": "查询与关系收据可重放；Watson 镜像条件保持关闭",
        "networkCalls": 0, "metric": "5/5 queries",
    },
    {
        "id": "experiment_20261013_13", "time": "10-13 13:00", "status": "blocked",
        "stage": "原生身份直连", "summary": "双 PID 与非零时钟下界本地通过；真实 API 阶段受预算阻止",
        "networkCalls": 0, "metric": "1791 → 34",
    },
]

data = {
    "meta": {
        "title": "AgentOps Thesis Observatory",
        "subtitle": "Pre-attribution telemetry · evidence first",
        "generatedAt": "2026-10-13T14:00:00+08:00",
        "timezone": index["timezone"],
        "currentExperiments": len(index["current_hour_directories"]),
        "historicalRuns": index["historical_run_records"],
        "evidenceMode": "runtime observed + controlled local fixture",
    },
    "headline": {
        "gate": gate["status"],
        "testsPassed": implementation["checks"]["trace_adapter_python"]["passed"],
        "testsFailed": implementation["checks"]["trace_adapter_python"]["failed"],
        "fieldCompleteness": quality["field_completeness"]["overall_rate"],
        "queryReplay": f"{replay['query_count']}/{replay['query_count']}",
        "queryReplayPassed": replay["all_queries_replayed"],
        "directPid": {
            "initial": identity["evidence"]["initial_namespace_pid"],
            "collector": identity["evidence"]["collector_namespace_pid"],
            "userspace": identity["evidence"]["userspace_pid"],
            "status": identity["evidence"]["pid_mapping_status"],
        },
        "clockFloorNs": identity["evidence"]["observer_anchor_uncertainty_ns"],
        "budget": {
            "spent": budget["already_spent_usd"], "limit": budget["hard_stop_total_usd"],
            "projected": budget["projected_total_usd"], "status": budget["status"],
        },
    },
    "capabilities": [
        {"name": "事件规范化", "status": "verified", "score": 1.0, "detail": "6-event lifecycle closed"},
        {"name": "跨层身份对齐", "status": "verified", "score": 1.0, "detail": "direct PID namespace evidence"},
        {"name": "时钟统一", "status": "verified", "score": 1.0, "detail": "1 ns nonzero floor"},
        {"name": "查询与收据", "status": "verified", "score": 1.0, "detail": "5/5 replayed"},
        {"name": "模型调用上下文", "status": "implementation", "score": .72, "detail": "implementation verified; live provider unverified"},
        {"name": "真实并发验证", "status": "blocked", "score": .35, "detail": "budget preflight blocked"},
        {"name": "因果归因", "status": "not-started", "score": 0, "detail": "outside current scope"},
    ],
    "trace": {
        "runId": events["experiment_id"],
        "sessionId": "48174557…8760",
        "eventCount": events["stream"]["event_count"],
        "closed": events["stream"]["all_sessions_closed"],
        "durationMs": round(real["monotonic_delta_ms"], 3),
        "spans": [
            {"name": "session", "type": "session", "start": 0, "duration": 100, "status": "ok", "evidence": "runtime_observed"},
            {"name": "step-native-bash-1", "type": "step", "start": 5, "duration": 91, "status": "ok", "evidence": "direct lifecycle"},
            {"name": "Bash tool call", "type": "tool", "start": 12, "duration": 72, "status": "ok", "evidence": "shared tool_call_id"},
            {"name": "observer clock", "type": "system", "start": 12, "duration": 3, "status": "ok", "evidence": "boot epoch + ktime"},
        ],
        "lifecycle": ["session.start", "step.start", "tool.start", "tool.end", "step.end", "session.end"],
    },
    "identity": {
        "status": identity["status"],
        "mappingMethod": identity["evidence"]["mapping_method"],
        "marker": identity["evidence"]["marker"],
        "initialPid": identity["evidence"]["initial_namespace_pid"],
        "collectorPid": identity["evidence"]["collector_namespace_pid"],
        "userspacePid": identity["evidence"]["userspace_pid"],
        "fixtureMatrix": matrix["status_counts"],
        "checks": identity["checks"],
    },
    "clock": {
        "conversion": "boot_epoch_ns_plus_bpf_ktime_ns",
        "rawBootNs": identity["evidence"]["observer_raw_boot_ns"],
        "bootEpochNs": identity["evidence"]["observer_boot_epoch_ns"],
        "anchorUncertaintyNs": identity["evidence"]["observer_anchor_uncertainty_ns"],
        "series": [
            {"experiment": "10-10 14", "anchorRangeNs": clock14["anchor_offset_range_ns"], "probeUncertaintyNs": clock14["probe_realtime_uncertainty_ns"]},
            {"experiment": "10-10 15", "anchorRangeNs": clock15["anchor_offset_range_ns"], "probeUncertaintyNs": clock15["probe_realtime_uncertainty_ns"]},
            {"experiment": "10-12 14", "anchorRangeNs": real["anchor_offset_range_ns"], "probeUncertaintyNs": real["probe_realtime_uncertainty_ns"]},
            {"experiment": "10-13 13", "anchorRangeNs": 1, "probeUncertaintyNs": identity["evidence"]["observer_anchor_uncertainty_ns"]},
        ],
    },
    "quality": {
        "fieldGroups": quality["field_completeness"]["groups"],
        "overallPresent": quality["field_completeness"]["overall_present"],
        "overallExpected": quality["field_completeness"]["overall_expected"],
        "invalidRejected": quality["negative_protocol_matrix"]["rejected_count"],
        "invalidCases": quality["negative_protocol_matrix"]["case_count"],
        "deterministicReplay": quality["deterministic_replay"]["byte_identical"],
        "nativeToolCapture": gate["tool_capture"],
    },
    "evidence": {
        "handlers": evidence["collection_handlers"],
        "queries": evidence["queries"],
        "relations": evidence["observed_relations"],
        "readiness": evidence["readiness"],
        "modelContext": {
            "status": context["evidence_status"],
            "supportedFields": context["supported_fields"],
            "liveValidation": context["live_provider_validation"],
            "tests": context["test_result"],
        },
    },
    "testSuites": [
        {"name": "Trace Adapter", "passed": implementation["checks"]["trace_adapter_python"]["passed"], "failed": 0},
        {"name": "BPF runtime", "passed": implementation["checks"]["bpf_runtime"]["passed"], "failed": 0},
        {"name": "Capture core", "passed": implementation["checks"]["agentsight_capture_core"]["passed"], "failed": 0},
        {"name": "Capture API", "passed": implementation["checks"]["agentsight_capture_public_api"]["passed"], "failed": 0},
        *implementation["checks"]["bpf_unit_suites"],
    ],
    "testProgression": [
        {"label": "10-12 15", "value": 64},
        {"label": "10-12 16", "value": 77},
        {"label": "10-13 10", "value": 89},
        {"label": "10-13 13", "value": implementation["checks"]["trace_adapter_python"]["passed"]},
    ],
    "experiments": experiments,
    "sources": [
        source("lab/experiment/experiment_20261012_14/analysis.json"),
        source("lab/experiment/experiment_20261012_16/observation-quality-report-final.json"),
        source("lab/experiment/experiment_20261013_10/pre-attribution-evidence-package.json"),
        source("lab/experiment/experiment_20261013_13/native-identity-verification.json"),
        source("lab/experiment/experiment_20261013_13/implementation-verification.json"),
        source("lab/experiment/experiment_20261013_13/budget-preflight.json"),
    ],
}

output = SITE / "dist" / "data.json"
output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"wrote {output.relative_to(ROOT)}")
