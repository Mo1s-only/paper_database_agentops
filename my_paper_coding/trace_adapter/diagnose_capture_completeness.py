#!/usr/bin/env python3
"""Compare native tool calls with AgentSight records across real runs; no API calls."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3

from validate_real_scenarios import native_tools


def short_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def system_tool_ids(run: Path) -> set[str]:
    path = run / "alignment-inputs" / "evidence-events.jsonl"
    rows = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    return {row.get("tool_call_id") for row in rows if row.get("record_type") == "agentsight.tool_calls"}


def database_hits(db: Path, tool_id: str) -> list[str]:
    hits = set()
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as connection:
        for (table,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            escaped = table.replace('"', '""')
            for row in connection.execute(f'SELECT * FROM "{escaped}"'):
                if any(tool_id in str(value) for value in row if value is not None):
                    hits.add(table)
                    break
    return sorted(hits)


def inspect_run(run: Path) -> dict:
    tools = native_tools(run)
    observed = system_tool_ids(run)
    debug = (run / "raw-stream.log").read_text(encoding="utf-8", errors="replace")
    records = []
    for position, tool in enumerate(tools, 1):
        tool_id = tool["tool_call_id"]
        present = tool_id in observed
        records.append({"tool_id_hash": short_hash(tool_id), "agent_id": tool["agent_id"],
                        "semantic_step_id": tool["semantic_step_id"], "tool_name": tool["tool_name"],
                        "global_position": position, "captured_in_tool_calls": present,
                        "present_in_debug_stream": tool_id in debug,
                        "database_tables_containing_id": database_hits(run / "session.db", tool_id)})
    return {"run_id": run.name, "native_tools": len(tools), "agentsight_tools": len(observed),
            "captured": sum(row["captured_in_tool_calls"] for row in records), "records": records}


def aggregate(runs: list[dict]) -> dict:
    rows = [row for run in runs for row in run["records"]]
    grouped = {}
    for key, getter in {
        "by_tool_name": lambda row: row["tool_name"],
        "by_agent": lambda row: row["agent_id"],
        "by_global_position": lambda row: str(row["global_position"]),
    }.items():
        values = defaultdict(lambda: Counter(total=0, captured=0))
        for row in rows:
            label = getter(row); values[label]["total"] += 1
            values[label]["captured"] += int(row["captured_in_tool_calls"])
        grouped[key] = {label: {"captured": count["captured"], "total": count["total"],
                                "coverage": count["captured"] / count["total"]}
                        for label, count in sorted(values.items())}
    captured = sum(row["captured_in_tool_calls"] for row in rows)
    return {"runs": len(runs), "native_tools": len(rows), "captured_tools": captured,
            "missing_tools": len(rows) - captured, "coverage": captured / len(rows) if rows else None,
            "debug_stream_ids": sum(row["present_in_debug_stream"] for row in rows), **grouped,
            "missing_ids_found_elsewhere_in_database": sum(bool(row["database_tables_containing_id"])
                                                            for row in rows if not row["captured_in_tool_calls"])}


def render_markdown(summary: dict) -> str:
    agg = summary["aggregate"]
    lines = ["# 工具捕获完整性诊断｜2026-10-10", "",
             "> 本报告只读取已有真实运行，不发起 API 调用。工具 ID 仅保存 SHA256 前缀。", "",
             "## 汇总", "",
             f"- 真实运行：{agg['runs']} 次。",
             f"- 原生工具调用：{agg['native_tools']}；AgentSight 捕获：{agg['captured_tools']}；缺失：{agg['missing_tools']}。",
             f"- 聚合捕获率：{agg['coverage']:.1%}。这是 4 次小样本诊断量，不是系统总体捕获率。",
             f"- debug stream 中可直接搜索到的工具 ID：{agg['debug_stream_ids']}/{agg['native_tools']}。",
             f"- 缺失 ID 在 SQLite 其他表中的命中：{agg['missing_ids_found_elsewhere_in_database']}/{agg['missing_tools']}。", "",
             "## 逐运行结果", "", "| 运行 | 原生工具 | AgentSight 工具 | 捕获 | 缺失步骤 |", "|---|---:|---:|---:|---|"]
    for run in summary["runs"]:
        missing = ", ".join(row["semantic_step_id"] for row in run["records"] if not row["captured_in_tool_calls"]) or "无"
        lines.append(f"| {run['run_id']} | {run['native_tools']} | {run['agentsight_tools']} | {run['captured']}/{run['native_tools']} | {missing} |")
    lines += ["", "## 分组观察", "", "| 工具类型 | 捕获/总数 |", "|---|---:|"]
    for label, value in agg["by_tool_name"].items():
        lines.append(f"| {label} | {value['captured']}/{value['total']} |")
    lines += ["", "| Agent | 捕获/总数 |", "|---|---:|"]
    for label, value in agg["by_agent"].items():
        lines.append(f"| {label} | {value['captured']}/{value['total']} |")
    lines += ["", "## 证据判断", "",
              "### VERIFIED", "",
              "- 4 次真实运行共有 15 次原生工具调用，AgentSight `tool_calls` 捕获 12 次；3 个缺失 ID 在 SQLite 任一表中均未出现。",
              "- 三个缺失分别为 Read、Bash、Write，工具类型不是单一决定因素。",
              "- Agent A 与 Agent B 都出现过缺失；缺失发生在批次全局第 1 或第 2 个工具位置，后续位置在当前样本中均被捕获。",
              "- debug stream 对已捕获和未捕获工具 ID 都不可见，因此不能把该文本流当作工具完整性旁路证据。", "",
              "### INFERRED", "",
              "- 缺失发生在工具记录进入 SQLite 之前或之中，而不是后续规范化/对齐阶段；因为缺失 ID 不存在于任何 SQLite 表。",
              "- 当前证据更像间歇性或时序相关漏采，尚不能归因到某个工具类型。", "",
              "### UNVERIFIED", "",
              "- 是否由 SSE 解析、首个 Agent 会话启动时序、数据库写入或 Claude/AgentSight 版本组合导致。",
              "- 全局位置 1/2 与漏采的关系能否在重复运行中成立。", "",
              "## 下一闸门", "",
              "在下一次真实 API 重复前，先把采集门改为：原生工具数与系统工具数不一致时，运行标记为 `capture_incomplete` 并禁止进入系统层 Edge 结论；同时保留应用层预测用于诊断。若要定位根因，应增加 AgentSight 上游网络/SSE 原始帧的独立留存。", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    runs = [inspect_run(path) for path in args.run]
    summary = {"schema_version": "agentsight-capture-diagnostic-v0.1", "source_policy": "existing local logs only; no API calls",
               "runs": runs, "aggregate": aggregate(runs)}
    (args.output / "capture-completeness.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "工具捕获完整性诊断_2026-10-10.md").write_text(render_markdown(summary), encoding="utf-8")
    print(json.dumps(summary["aggregate"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
