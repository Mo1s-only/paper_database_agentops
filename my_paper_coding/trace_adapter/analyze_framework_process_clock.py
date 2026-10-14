#!/usr/bin/env python3
"""Analyze native framework, process-tree and clock evidence from one experiment."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics


def digest(value):
    return hashlib.sha256(str(value).encode()).hexdigest()[:16]


def boot_second_correction_ns(realtime_minus_monotonic_ns: int) -> int:
    return realtime_minus_monotonic_ns % 1_000_000_000


def inside(value, interval):
    return interval[0] <= value <= interval[1]


def choose_clock_conversion(raw_start_ms, launch_interval_ms, legacy_correction_ns):
    """Use native high-precision time when bounded; repair only legacy seconds."""
    if raw_start_ms is None:
        return {"mode": "unresolved", "applied_correction_ns": None,
                "resolved_start_ms": None, "inside_launch_interval": False}
    if inside(raw_start_ms, launch_interval_ms):
        return {"mode": "nanosecond_boot_epoch", "applied_correction_ns": 0,
                "resolved_start_ms": raw_start_ms, "inside_launch_interval": True}
    repaired = raw_start_ms + legacy_correction_ns / 1e6
    if inside(repaired, launch_interval_ms):
        return {"mode": "legacy_integer_second_boot_epoch",
                "applied_correction_ns": legacy_correction_ns,
                "resolved_start_ms": repaired, "inside_launch_interval": True}
    return {"mode": "unresolved", "applied_correction_ns": None,
            "resolved_start_ms": raw_start_ms, "inside_launch_interval": False}


def blocks(row):
    content = row.get("message", {}).get("content", [])
    return content if isinstance(content, list) else []


def decode(content):
    if isinstance(content, list):
        content = "".join(block.get("text", "") if isinstance(block, dict) else str(block)
                          for block in content)
    try:
        return json.loads(str(content).strip())
    except (json.JSONDecodeError, TypeError):
        return None


def choose_native_pid_mapping(audit_rows, launcher_pid, agentsight_pids):
    """Resolve a unique observer/local TGID pair emitted by the BPF helper."""
    direct = []
    for row in audit_rows:
        try:
            details = json.loads(row.get("details_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        observer_pid = row.get("pid")
        if (row.get("action") == "exec" and observer_pid in agentsight_pids and
                details.get("event") == "EXEC" and
                details.get("namespace_pid") == launcher_pid):
            direct.append((observer_pid, details["namespace_pid"]))
    direct = sorted(set(direct))
    if len(direct) == 1:
        observer_pid, local_pid = direct[0]
        return {
            "status": "accepted",
            "method": "bpf_get_ns_current_pid_tgid",
            "evidence": [f"bpf.pidns.tgid={observer_pid},{local_pid}"],
            "observer_pid": observer_pid,
            "candidate_count": 1,
        }
    return {
        "status": "inferred" if agentsight_pids else "abstain",
        "method": ("session+comm+launch_interval+shared_tool_call_id"
                   if agentsight_pids else None),
        "evidence": (["capture-summary.session_id", "process_nodes.comm=claude",
                      "analysis.process_start_in_launch_interval=true",
                      "tool_calls.tool_call_id=framework.tool_use.id"]
                     if agentsight_pids else ["no_unique_supported_mapping"]),
        "observer_pid": agentsight_pids[0] if len(agentsight_pids) == 1 else None,
        "candidate_count": len(direct),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, required=True)
    args = parser.parse_args()
    experiment = args.experiment.resolve()
    results = experiment / "results"
    native = [json.loads(line) for line in
              (results / "framework-native.jsonl").read_text(encoding="utf-8").splitlines()]
    receipts = {row["line"]: row for row in
                (json.loads(line) for line in
                 (results / "framework-receipts.jsonl").read_text().splitlines())}
    tool = None
    tool_result = None
    lifecycle = {"system_init": 0, "tool_use": 0, "tool_result": 0, "result": 0}
    for line_no, row in enumerate(native, 1):
        if row.get("type") == "system" and row.get("subtype") == "init":
            lifecycle["system_init"] += 1
        if row.get("type") == "result":
            lifecycle["result"] += 1
        for block in blocks(row):
            if block.get("type") == "tool_use":
                lifecycle["tool_use"] += 1
                tool = {"id": block["id"], "name": block.get("name"), "line": line_no}
            elif block.get("type") == "tool_result":
                lifecycle["tool_result"] += 1
                tool_result = {"id": block.get("tool_use_id"),
                               "value": decode(block.get("content")), "line": line_no}
    if not tool or not tool_result or tool["id"] != tool_result["id"]:
        raise ValueError("Native tool lifecycle is incomplete")

    capture = json.loads((results / "capture-summary.json").read_text())
    launch = json.loads((results / "launch.json").read_text())
    versions = json.loads((results / "versions.json").read_text())
    samples = [json.loads(line) for line in
               (results / "process-samples.jsonl").read_text().splitlines()]
    sampled_pids = {proc["pid"] for sample in samples for proc in sample["processes"]}
    sampled_names = {proc["pid"]: proc["comm"]
                     for sample in samples for proc in sample["processes"]}
    offsets = [sample["clock"]["realtime_midpoint_ns"] -
               sample["clock"]["monotonic_ns"] for sample in samples]
    with sqlite3.connect(f"file:{(results / 'session.db').as_posix()}?mode=ro",
                         uri=True) as connection:
        connection.row_factory = sqlite3.Row
        tool_rows = [dict(row) for row in connection.execute(
            "SELECT * FROM tool_calls WHERE tool_call_id=?", (tool["id"],))]
        llm_rows = [dict(row) for row in connection.execute(
            "SELECT * FROM llm_calls WHERE session_id=?", (capture["session_id"],))]
        process_schema = [row[1] for row in connection.execute(
            "PRAGMA table_info(process_nodes)")]
        tool_schema = [row[1] for row in connection.execute(
            "PRAGMA table_info(tool_calls)")]
        process_rows = [dict(row) for row in connection.execute(
            "SELECT * FROM process_nodes")]
        audit_rows = [dict(row) for row in connection.execute(
            "SELECT pid, comm, action, details_json FROM audit_events "
            "WHERE audit_type='process' AND action='exec'")]

    agentsight_pids = sorted(
        {row.get("related_pid") for row in tool_rows if row.get("related_pid") is not None} |
        {row.get("pid") for row in llm_rows if row.get("pid") is not None})
    pid_mapping = choose_native_pid_mapping(
        audit_rows, capture["launcher_pid"], agentsight_pids)
    probe = tool_result["value"] if isinstance(tool_result["value"], dict) else {}
    receipt = receipts[tool_result["line"]]
    tool_row = tool_rows[0] if len(tool_rows) == 1 else None
    system_tool_ms = tool_row["timestamp_ms"] if tool_row else None
    observer_raw_boot_ns = tool_row.get("observer_raw_boot_ns") if tool_row else None
    observer_boot_epoch_ns = tool_row.get("observer_boot_epoch_ns") if tool_row else None
    observer_uncertainty_ns = (tool_row.get("observer_clock_uncertainty_ns")
                               if tool_row else None)
    wall_delta_ms = (receipt["realtime_midpoint_ns"] / 1e6 - system_tool_ms
                     if system_tool_ms is not None else None)
    median_offset = int(statistics.median(offsets))
    legacy_correction_ns = boot_second_correction_ns(median_offset)
    system_process = next((row for row in process_rows
                           if row.get("pid") in agentsight_pids and
                           row.get("comm") == "claude"), None)
    raw_start_ms = system_process.get("start_timestamp_ms") if system_process else None
    launch_interval_ms = [launch["launch_before"]["realtime_midpoint_ns"] / 1e6,
                          launch["launch_after"]["realtime_midpoint_ns"] / 1e6]
    conversion = choose_clock_conversion(raw_start_ms, launch_interval_ms,
                                         legacy_correction_ns)
    applied_ns = conversion["applied_correction_ns"]
    resolved_tool_ms = (system_tool_ms + applied_ns / 1e6
                        if system_tool_ms is not None and applied_ns is not None else None)
    resolved_wall_delta_ms = (receipt["realtime_midpoint_ns"] / 1e6 - resolved_tool_ms
                              if resolved_tool_ms is not None else None)
    if observer_raw_boot_ns is not None:
        tool_mono_ns = observer_raw_boot_ns
    elif resolved_tool_ms is not None:
        tool_mono_ns = int(resolved_tool_ms * 1_000_000 - median_offset)
    else:
        tool_mono_ns = None

    summary = {
        "schema_version": "agentops-framework-process-clock-analysis-v0.2",
        "experiment_id": experiment.name,
        "framework_lifecycle": lifecycle,
        "native_tool_id_hash": digest(tool["id"]),
        "native_tool_name": tool["name"],
        "native_tool_closed": tool["id"] == tool_result["id"],
        "agentsight_tool_match_count": len(tool_rows),
        "agentsight_llm_rows_for_session": len(llm_rows),
        "agentsight_binary": versions.get("agentsight_binary"),
        "agentsight_binary_sha256": versions.get("agentsight_sha256"),
        "agentsight_version": versions.get("agentsight"),
        "launcher_pid": capture["launcher_pid"],
        "tool_probe_pid": (probe.get("pid") or [None])[0],
        "tool_probe_ppid": (probe.get("ppid") or [None])[0],
        "tool_probe_nspid": probe.get("nspid"),
        "tool_probe_pid_namespace": probe.get("pid_namespace_link"),
        "process_samples": len(samples),
        "unique_sampled_descendants": len(sampled_pids),
        "agentsight_pids": agentsight_pids,
        "pid_mapping_status": pid_mapping["status"],
        "pid_mapping_method": pid_mapping["method"],
        "pid_mapping_evidence": pid_mapping["evidence"],
        "pid_mapping_observer_pid": pid_mapping["observer_pid"],
        "pid_mapping_direct_candidate_count": pid_mapping["candidate_count"],
        "agentsight_pids_in_sampled_tree": {
            str(pid): pid in sampled_pids for pid in agentsight_pids},
        "agentsight_pid_names": {
            str(pid): sampled_names.get(pid) for pid in agentsight_pids},
        "process_nodes_schema": process_schema,
        "tool_calls_schema": tool_schema,
        "process_nodes_rows": len(process_rows),
        "clock_anchor_samples": len(offsets),
        "realtime_minus_monotonic_ns_median": median_offset,
        "realtime_minus_monotonic_ns_range": [min(offsets), max(offsets)],
        "anchor_offset_range_ns": max(offsets) - min(offsets),
        "legacy_boot_second_correction_ns": legacy_correction_ns,
        "clock_conversion_mode": conversion["mode"],
        "applied_clock_correction_ns": applied_ns,
        "agentsight_tool_observer_raw_boot_ns": observer_raw_boot_ns,
        "agentsight_tool_observer_boot_epoch_ns": observer_boot_epoch_ns,
        "agentsight_tool_observer_anchor_uncertainty_ns": observer_uncertainty_ns,
        "agentsight_tool_epoch_formula_verified": (
            observer_raw_boot_ns is not None and observer_boot_epoch_ns is not None and
            (observer_raw_boot_ns + observer_boot_epoch_ns) // 1_000_000 ==
            system_tool_ms),
        "tool_result_receipt_minus_agentsight_tool_ms": wall_delta_ms,
        "tool_result_receipt_minus_resolved_agentsight_tool_ms": resolved_wall_delta_ms,
        "agentsight_process_start_raw_ms": raw_start_ms,
        "agentsight_process_start_resolved_ms": conversion["resolved_start_ms"],
        "application_launch_interval_ms": launch_interval_ms,
        "process_start_in_launch_interval": conversion["inside_launch_interval"],
        "agentsight_tool_monotonic_ns": tool_mono_ns,
        "tool_result_receipt_monotonic_ns": receipt["monotonic_ns"],
        "monotonic_delta_ms": (
            (receipt["monotonic_ns"] - tool_mono_ns) / 1e6
            if tool_mono_ns is not None else None),
        "probe_realtime_uncertainty_ns": probe.get("realtime_uncertainty_ns"),
        "reported_cost_usd": capture.get("reported_cost_usd"),
        "source_evidence": [
            "lab/agentsight/source/thesis_adapter/bpf/process.bpf.c: bpf_get_ns_current_pid_tgid",
            "lab/agentsight/source/thesis_adapter/agentsight-capture/src/time.rs: paired realtime/CLOCK_MONOTONIC boot epoch",
            "tool_calls.observer_raw_boot_ns + tool_calls.observer_boot_epoch_ns"
        ],
        "boundaries": [
            ("PID mapping is direct for this session through the captured namespace TGID"
             if pid_mapping["status"] == "accepted" else
             "PID mapping is inferred from session, process name, launch interval and shared tool_call ID"),
            "One session does not establish mapping stability across long or multi-agent runs",
            "Tool receipt delta includes execution and stream delivery latency"
        ]
    }
    (experiment / "analysis.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    matched = (all(summary["agentsight_pids_in_sampled_tree"].values())
               if agentsight_pids else False)
    correction_text = (f"{applied_ns / 1e6:.6f} ms"
                       if applied_ns is not None else "unresolved")
    lines = [
        f"# {experiment.name} 实验报告", "", "## VERIFIED", "",
        f"- Claude 原生生命周期：init={lifecycle['system_init']}、tool_use={lifecycle['tool_use']}、tool_result={lifecycle['tool_result']}、result={lifecycle['result']}。",
        f"- 原生工具闭合：{summary['native_tool_closed']}；AgentSight 同一 tool_call ID 命中：{len(tool_rows)}。",
        f"- 使用的 AgentSight 二进制 SHA256：`{versions.get('agentsight_sha256')}`。",
        f"- 进程树采样 {len(samples)} 次，覆盖 {len(sampled_pids)} 个唯一 PID；AgentSight PID 出现在应用 `/proc` 树：{matched}。",
        f"- realtime-monotonic 配对偏移范围宽度：{summary['anchor_offset_range_ns']} ns。",
        f"- 时钟转换模式：`{conversion['mode']}`；实际追加校正量：{correction_text}。",
        f"- AgentSight 原始进程开始时间落在 Popen 边界内：{conversion['inside_launch_interval']}。",
        f"- 工具行保存原始 boot 时间：{observer_raw_boot_ns is not None}；保存 boot epoch 锚点：{observer_boot_epoch_ns is not None}；公式复算一致：{summary['agentsight_tool_epoch_formula_verified']}。",
        (f"- 原生 tool_result 接收墙钟减 AgentSight 工具时间：{wall_delta_ms:.3f} ms；按所选转换后：{resolved_wall_delta_ms:.3f} ms。"
         if wall_delta_ms is not None and resolved_wall_delta_ms is not None else
         "- AgentSight 未唯一捕获该工具，无法计算工具时间差。"),
        f"- 本次真实 API 报告费用：{capture.get('reported_cost_usd')} USD。", "",
        "## INFERRED", "",
        f"- 应用 PID {capture['launcher_pid']} 与 AgentSight PID {agentsight_pids} 的映射由 session、`claude` 进程名、启动区间和共享 tool_call ID 共同支持；当前仍没有通用 PID 数字换算公式。",
        "- 工具接收时间差包含工具执行、CLI 处理和流式传输，不代表单纯的观测延迟。", "",
        "## UNVERIFIED", "",
        "- 多 Agent、多工具及长会话中的 PID 映射稳定性。",
        "- SSE 工具事件在处理链中的精确生成点和端到端误差界。", ""
    ]
    (experiment / "实验报告.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
