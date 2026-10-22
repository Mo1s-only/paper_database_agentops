#!/usr/bin/env python3
"""Build the dashboard data snapshot from traceable experiment artifacts."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


SITE = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[3]
EXP = ROOT / "lab" / "experiment"
STRESS_FIXTURES = ROOT / "my_paper_coding" / "trace_adapter" / "fixtures" / "alignment_stress_1000.jsonl"
AGENTRX_SAMPLE = "lab/AgentRx/trajectories/tau-retail/instruction_adherence_failure.json"
COMPATIBILITY_REPORT = "lab/experiment/experiment_20261016_16/results_r3/compatibility-report.json"


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
batch_manifest = load("my_paper_coding/experiment_control/real-api-error-agentrx-20261019.json")
batch_preflight = load("lab/experiment/experiment_20261019_18/preflight.json")
compatibility = load(COMPATIBILITY_REPORT)
agentrx_path = ROOT / AGENTRX_SAMPLE
agentrx_steps = len(load(AGENTRX_SAMPLE)["traj"]) if agentrx_path.exists() else None
stress_fixture_count = sum(1 for line in STRESS_FIXTURES.open(encoding="utf-8") if line.strip())

dataset_modes = [
    {"id": "cross_layer_live", "label": "真实跨层采集", "description": "Claude Code 原生事件 + AgentSight 系统观测；需 WSL、凭据和预算预检"},
    {"id": "semantic_diagnosis", "label": "公开轨迹语义诊断", "description": "模型分析已有轨迹；不产生配对的系统侧观测"},
    {"id": "adapter_compatibility", "label": "公开数据适配", "description": "离线检查 schema、标签与证据定位；不调用 API"},
    {"id": "synthetic_stress", "label": "合成压力校验", "description": "确定性 fixture；不代表真实捕获率"},
]

dataset_catalog = [
    {
        "id": scenario, "name": scenario, "mode": "cross_layer_live", "recordCount": 1,
        "inputPath": "my_paper_coding/trace_adapter/capture_real_scenarios.py",
        "selector": scenario, "available": True, "apiRequired": True,
        "pairedSystemObservations": "on_new_run", "evidenceBoundary": "受控任务定义；只有真实运行后才能评估跨层捕获与对齐",
        "executionNote": "真实调用仅在本地控制器预检全部通过后启动；当前授权批次只含 error-propagation-v1 与后续 AgentRx #12。",
    }
    for scenario in ("error-propagation-v1", "routing-error-v1")
]
dataset_catalog.append({
    "id": "agentrx-tau12", "name": "AgentRx · Tau Retail #12", "mode": "semantic_diagnosis",
    "recordCount": 1, "stepCount": agentrx_steps, "inputPath": AGENTRX_SAMPLE,
    "selector": "task_id=12; traj only", "available": agentrx_path.exists(), "apiRequired": True,
    "pairedSystemObservations": "none", "evidenceBoundary": "公开单条轨迹；仅能验证语义诊断，不能验证 AgentSight 跨层采集",
    "executionNote": "模型输入必须排除 task.actions、reward_info 与独立真值；本批次仅在 error-propagation-v1 成功后顺序执行。",
})
public_dataset_ids = {"Who&When": "who-when", "TRAIL": "trail", "AgentTrace": "agenttrace"}
public_dataset_boundaries = {
    "Who&When": "责任 Agent/Step 标签可用；传播边与因果路径缺失时必须拒判",
    "TRAIL": "步骤标签部分可用；责任 Agent/边/路径不能补造",
    "AgentTrace": "公开轨迹标签适配；没有本地配对的 AgentSight 系统事件",
}
for report in compatibility["datasets"]:
    input_path = f"lab/experiment/experiment_20261016_16/results_r3/{report['output']}"
    dataset_catalog.append({
        "id": public_dataset_ids[report["dataset"]], "name": report["dataset"],
        "mode": "adapter_compatibility", "recordCount": report["records"],
        "inputPath": input_path, "selector": "all normalized records",
        "available": (ROOT / input_path).exists(), "apiRequired": False,
        "pairedSystemObservations": "none", "evidenceBoundary": public_dataset_boundaries[report["dataset"]],
        "executionNote": "只检查公开数据适配与兼容性；不能作为真实跨层采集结果。",
    })
dataset_catalog.append({
    "id": "alignment-stress-1000", "name": "Alignment stress · 1,000 fixtures",
    "mode": "synthetic_stress", "recordCount": stress_fixture_count,
    "inputPath": "my_paper_coding/trace_adapter/fixtures/alignment_stress_1000.jsonl",
    "selector": "all fixtures", "available": STRESS_FIXTURES.exists(), "apiRequired": False,
    "pairedSystemObservations": "synthetic_only", "evidenceBoundary": "合成 oracle；当前尚未运行生产对齐器",
    "executionNote": "零 API 离线输入，不能推断真实 AgentSight 捕获率。",
})

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
    {
        "id": "experiment_20261016_16", "time": "10-16 16:00", "status": "verified",
        "stage": "公开数据适配", "summary": "三套公开数据的 schema/标签兼容性，不含配对系统事件",
        "networkCalls": 0, "metric": f"{compatibility['overall']['records']} records",
        "datasetIds": ["who-when", "trail", "agenttrace"], "datasetEvidence": "verified_input",
    },
    {
        "id": "experiment_20261019_18", "time": "10-19 18:00", "status": "blocked",
        "stage": "真实 API 小样本预检", "summary": "重启后 WSL 功能已启用，但未安装 Ubuntu；真实 API 未调用",
        "networkCalls": 0, "metric": "0 new API calls",
        "datasetIds": ["error-propagation-v1", "agentrx-tau12"], "datasetEvidence": "planned_only",
    },
]

data = {
    "meta": {
        "title": "AgentOps Thesis Observatory",
        "subtitle": "Pre-attribution telemetry · evidence first",
        "generatedAt": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "timezone": index["timezone"],
        "currentExperiments": len(experiments),
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
            "spent": batch_manifest["baseline_ledger_total_usd"],
            "limit": batch_manifest["hard_stop_total_usd"],
            "projected": round(batch_manifest["baseline_ledger_total_usd"] + batch_manifest["planned_batch_budget_usd"], 6),
            "status": "BLOCKED" if not batch_preflight["historical_ledger_reconciled"] else "PREFLIGHT_REQUIRED",
            "batchCapCny": batch_manifest["batch_cap_cny"],
            "plannedBatchCny": batch_manifest["planned_batch_budget_cny"],
            "ledgerReconciled": batch_preflight["historical_ledger_reconciled"],
            "sourceStatus": "frozen_historical_ledger_not_reconciled",
        },
    },
    "capabilities": [
        {"name": "事件规范化", "status": "verified", "score": 1.0, "detail": "6-event lifecycle closed"},
        {"name": "跨层身份对齐", "status": "verified", "score": 1.0, "detail": "direct PID namespace evidence"},
        {"name": "时钟统一", "status": "verified", "score": 1.0, "detail": "1 ns nonzero floor"},
        {"name": "查询与收据", "status": "verified", "score": 1.0, "detail": "5/5 replayed"},
        {"name": "模型调用上下文", "status": "implementation", "score": .72, "detail": "implementation verified; live provider unverified"},
        {"name": "真实并发验证", "status": "blocked", "score": .35, "detail": "Ubuntu distro + ledger reconciliation pending"},
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
    "captureIntegrity": {
        "status": "reported_with_unresolved_root_cause",
        "evidenceStatus": "VERIFIED_IN_LOCAL_REPORT",
        "reproducedFromRawRuns": False,
        "aggregate": {
            "runs": 4, "nativeToolCalls": 15, "capturedToolCalls": 12,
            "missingToolCalls": 3, "coverage": 12 / 15,
            "missingIdsInSqlite": 0, "matchingIdsInDebugStream": 0,
        },
        "observations": [
            "3 个缺失调用分别涉及 Read、Bash、Write；不是单一工具类型。",
            "缺失出现在批次全局第 1 或第 2 个工具位置；当前样本不足以证明位置导致漏采。",
            "缺失调用 ID 未出现在 SQLite 任一表，debug stream 也不能提供调用 ID 旁路证据。",
        ],
        "scenarios": [
            {"scenario": "error-propagation-v1", "missingStep": "agent_a.bash_1",
             "systemAlignment": "abstain", "nativeCalls": 4, "systemCalls": 3},
            {"scenario": "routing-error-v1", "missingStep": "agent_a.write_1",
             "systemAlignment": "accepted", "nativeCalls": 4, "systemCalls": 3},
        ],
        "inference": "更可能是事件进入 SQLite 之前或写入过程中丢失；尚不能区分 SSE 解析、启动时序、数据库写入或版本组合。",
        "futureInstrumentation": "真实采集脚本现在会写 observer-lifecycle.jsonl，记录 recorder/debug 的启动、就绪、每个 Agent 会话前后及退出状态；这只能排查进程存活和时序，不能单独定位 SSE 解析或 SQLite 写入故障。",
        "nextGate": "先用无 API 可重放输入验证生命周期记录，再增加 AgentSight 上游 SSE/网络原始帧留存，以定位事件在哪个采集阶段消失。",
        "sources": [
            "my_paper_coding/trace_adapter/README.md",
            "my_paper_coding/trace_adapter/真实跨故障扩展实验报告_2026-10-10.md",
        ],
        "rawEvidenceNote": "本工作区未包含对应的 real_application_runs 原始目录；此面板展示本地报告中的诊断结果，不能替代原始数据复核。",
    },
    "datasetExpansion": {
        "status": "synthetic_stress_set_ready_real_api_blocked_by_cumulative_budget",
        "syntheticFixtureCount": stress_fixture_count,
        "syntheticFixtureEvidenceKind": "synthetic_fixture",
        "syntheticFixtureApiCalls": 0,
        "syntheticFixtureProductionAlignerExercised": False,
        "publicAdapterRecords": 882,
        "realFaultClasses": 3,
        "existingRealRepeatsPerClass": 1,
        "plannedAdditionalRepeatsPerClass": 3,
        "plannedAdditionalRuns": 9,
        "perExperimentCapCny": 2.0,
        "perExperimentPlannedUpperCny": 1.92,
        "plannedBatchUpperCny": 17.28,
        "planningUsdCnyRate": 8.0,
        "historicalSpendUsd": 2.183708,
        "existingHardStopUsd": 2.0,
        "networkCallsMade": 0,
        "note": "计划尚未执行；单次上限已进采集脚本，累计预算仍超原硬停止线。",
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
    "datasetModes": dataset_modes,
    "datasetCatalog": dataset_catalog,
    "sources": [
        source("lab/experiment/experiment_20261012_14/analysis.json"),
        source("lab/experiment/experiment_20261012_16/observation-quality-report-final.json"),
        source("lab/experiment/experiment_20261013_10/pre-attribution-evidence-package.json"),
        source("lab/experiment/experiment_20261013_13/native-identity-verification.json"),
        source("lab/experiment/experiment_20261013_13/implementation-verification.json"),
        source("lab/experiment/experiment_20261013_13/budget-preflight.json"),
        source("my_paper_coding/experiment_control/real-api-error-agentrx-20261019.json"),
        source("my_paper_coding/trace_adapter/真实跨故障扩展实验报告_2026-10-10.md"),
        source("my_paper_coding/trace_adapter/README.md"),
        source(COMPATIBILITY_REPORT),
        source("lab/experiment/experiment_20261019_18/preflight.json"),
        source("lab/experiment/experiment_20261019_18/wsl-diagnosis.json"),
        source("my_paper_coding/trace_adapter/fixtures/alignment_stress_1000.jsonl"),
        *([source(AGENTRX_SAMPLE)] if agentrx_path.exists() else []),
    ],
}

paid_state_paths = (EXP / "experiment_20261019_18" / "results").glob("run-*/state.json")
paid_states = []
for state_path in paid_state_paths:
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("kind") == "authorized_live_batch":
            paid_states.append((state.get("created_at", ""), state_path, state))
    except (OSError, ValueError):
        continue
if paid_states:
    _, state_path, state = max(paid_states)
    run_dir = state_path.parent
    run_id = state["run_id"]
    result = state.get("result") or {}
    experiment = next(item for item in data["experiments"] if item["id"] == "experiment_20261019_18")
    experiment.update(
        time=state["created_at"][5:16].replace("T", " "),
        status="partial" if state.get("status") == "PARTIAL" else "blocked",
        stage="真实 API 小样本",
        summary="两会话与 AgentRx 已执行；AgentSight 工具捕获 0/4，系统侧归因拒判" if state.get("status") == "PARTIAL" else "真实批次执行中或尚未完成",
        metric=f"{result.get('api_calls', '?')} CLI sessions · 0/4 system tools" if state.get("status") == "PARTIAL" else state.get("stage", "unknown"),
        networkCalls="3 CLI 会话" if state.get("status") == "PARTIAL" else "未核定",
        datasetEvidence="runtime_observed_partial" if state.get("status") == "PARTIAL" else "run_in_progress",
    )
    if state.get("status") == "PARTIAL" and isinstance(result.get("error_reported_cost_usd"), (int, float)) and isinstance(result.get("agentrx_reported_cost_usd"), (int, float)):
        incremental = result["error_reported_cost_usd"] + result["agentrx_reported_cost_usd"]
        data["headline"]["budget"].update(status="PARTIAL", reportedIncrementalUsd=incremental,
                                              reportedIncrementalCnyAtRate=result.get("combined_cny_at_planning_rate"),
                                              sourceStatus="CLI_reported_increment_only; historical_baseline_unverified")
        data["capabilities"][5].update(status="partial", score=0.4,
                                         detail="2 real agent sessions; 4 native tools, 0 AgentSight tool records")
    data["sources"].append(source(str(state_path.relative_to(ROOT)).replace("\\", "/")))
    for relative in ("error-propagation/scenario-validation-report.json", "agentrx-tau12/score.json"):
        artifact = run_dir / relative
        if artifact.is_file():
            data["sources"].append(source(str(artifact.relative_to(ROOT)).replace("\\", "/")))

output = SITE / "dist" / "data.json"
output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"wrote {output.relative_to(ROOT)}")
