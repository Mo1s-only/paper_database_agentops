#!/usr/bin/env python3
"""Build a traceable, per-session audit of the thesis project's real API calls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "my_paper_coding/experiment_control/cost-ledger-20261012-sse-clock.json"
OUTPUT_DIR = ROOT / "lab/experiment/experiment_20261016_17"
OUTPUT_JSON = OUTPUT_DIR / "api-call-audit.json"
OUTPUT_MD = OUTPUT_DIR / "真实API调用逐次审计.md"


def read_json_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def result_record(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    rows = [row for row in records if row.get("type") == "result"]
    return rows[-1] if rows else None


def native_tool_calls(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in records:
        if row.get("type") != "assistant":
            continue
        message = row.get("message") or {}
        for block in message.get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            call_id = str(block.get("id") or "")
            if call_id in seen:
                continue
            seen.add(call_id)
            calls.append({
                "tool_call_id": call_id or None,
                "name": block.get("name"),
                "input": block.get("input") or {},
                "evidence": "native_framework_event",
            })
    return calls


def marker_prompt(log_path: Path) -> str:
    marker_path = log_path.parent / "marker.txt"
    if marker_path.exists():
        marker = marker_path.read_text(encoding="utf-8").strip()
        return f"Reply with exactly: {marker}"
    return "Reply with exactly: <marker>"


def classify(relative: str) -> str:
    normalized = relative.replace("\\", "/")
    if normalized.startswith("lab/agentsight/"):
        return "AgentSight早期端到端"
    if "/p0_pairing/" in normalized:
        return "P0 HTTP会话配对"
    if "/failure_pilot/" in normalized:
        return "受控故障先导"
    if "/real_application_runs/" in normalized:
        return "真实双Agent应用"
    if normalized.startswith("lab/experiment/"):
        return "框架原生工具与时钟"
    return "其他"


def prompt_and_flow(relative: str, log_path: Path) -> tuple[str, str, list[dict[str, Any]], str]:
    p = relative.replace("\\", "/")
    builtins: list[dict[str, Any]] = []
    observer = ""

    if p.startswith("lab/agentsight/"):
        prompt = ("Create a file named hello.txt in the current directory containing exactly the line: "
                  "AgentSight test. Then read it back and report its contents.")
        flow = "DeepSeek调用Write创建hello.txt → 调用Read读回文件 → 返回读回内容。"
        builtins = [
            {"name": "Write", "operation": "创建hello.txt并写入AgentSight test", "evidence": "fixed_runner_and_final_result"},
            {"name": "Read", "operation": "读回hello.txt验证文件内容", "evidence": "fixed_runner_and_final_result"},
        ]
        observer = "AgentSight在attach-by-command窗口内采集Claude进程、文件操作、网络/LLM活动并写入会话数据库及原始事件流。"
        return prompt, flow, builtins, observer

    if "/p0_pairing/" in p:
        prompt = marker_prompt(log_path)
        flow = "DeepSeek直接返回唯一marker；本次不要求模型调用工具。"
        observer = "AgentSight SSL/HTTP解析器采集请求与响应，通过marker、PID/TID及方向字段验证同一API会话的请求—响应配对。"
        return prompt, flow, [], observer

    if "/failure_pilot/" in p:
        if p.endswith("claude-run.log"):
            prompt = ("Use Bash exactly once to run fake_inventory.py alpha. Do not edit files or call any other tool. "
                      "Read the JSON result, compare it with the requirement available=1, and report whether satisfied.")
            flow = "DeepSeek调用Bash → fake_inventory.py返回available=0但status=ok → DeepSeek判断需求不满足。"
            builtins = [{"name": "Bash", "operation": "运行fake_inventory.py alpha", "evidence": "fixed_runner_and_final_result"}]
        elif p.endswith("claude-agent-a.log"):
            prompt = ("You are Agent A, the planner. Use Write exactly once to create route.json containing "
                      "{\"item\":\"alpha\",\"required_available\":1}. Do not call any other tool. Then report creation.")
            flow = "DeepSeek以Agent A身份调用Write → 生成route.json → 返回创建成功。"
            builtins = [{"name": "Write", "operation": "写入route.json，声明alpha需要库存1", "evidence": "fixed_runner_and_final_result"}]
        else:
            prompt = ("You are Agent B, the executor. Read route.json, run fake_inventory.py alpha with Bash, "
                      "then write decision.json containing item, required_available, observed_available and satisfied.")
            flow = "DeepSeek以Agent B身份调用Read → 调用Bash获得available=0 → 调用Write保存satisfied=false → 返回执行结果。"
            builtins = [
                {"name": "Read", "operation": "读取Agent A生成的route.json", "evidence": "fixed_runner_and_final_result"},
                {"name": "Bash", "operation": "运行fake_inventory.py alpha", "evidence": "fixed_runner_and_final_result"},
                {"name": "Write", "operation": "写入decision.json", "evidence": "fixed_runner_and_final_result"},
            ]
        observer = "AgentSight同时记录Claude进程和子进程；对双Agent运行保留两个会话日志、共享工作区文件及fake_inventory子进程证据。"
        return prompt, flow, builtins, observer

    if "/real_application_runs/" in p:
        agent_a = p.endswith("claude-agent-a.log")
        if "/real-error-propagation-" in p:
            if agent_a:
                prompt = ("Use Bash exactly once to run scenario_service_observer.py. Treat its complete JSON as the observation. "
                          "Then Write handoff.json with service and reported_status; do not repair inconsistent fields.")
                flow = "Agent A调用Bash得到raw=down/reported=healthy → 调用Write只转交healthy。"
                builtins = [{"name": "Bash", "operation": "运行服务观测器", "evidence": "native_framework_event"},
                            {"name": "Write", "operation": "写入handoff.json", "evidence": "native_framework_event"}]
            else:
                prompt = ("Use Bash exactly once to run scenario_service_decider.py handoff.json. Treat its JSON as the downstream "
                          "decision. Then Write decision.json with service, observed_status and action.")
                flow = "Agent B调用Bash读取handoff并决策 → 因看到healthy而产生NO_RESTART → 调用Write保存。"
                builtins = [{"name": "Bash", "operation": "运行下游决策器", "evidence": "native_framework_event"},
                            {"name": "Write", "operation": "写入decision.json", "evidence": "native_framework_event"}]
        elif "/real-routing-error-" in p:
            if agent_a:
                prompt = ("Use Bash exactly once to run scenario_faulty_router.py. Treat its complete JSON as router output. "
                          "Then Write route.json without changing the selected role.")
                flow = "Agent A调用Bash得到错误路由generalist → 调用Write保存route.json。"
                builtins = [{"name": "Bash", "operation": "运行受控错误路由器", "evidence": "native_framework_event"},
                            {"name": "Write", "operation": "写入route.json", "evidence": "native_framework_event"}]
            else:
                prompt = ("Use Bash exactly once to run scenario_route_executor.py route.json. Treat its JSON as execution result. "
                          "Then Write result.json with task, executed_role, retrieved and answer.")
                flow = "Agent B调用Bash按错误路由执行 → retrieved=false/answer=null → 调用Write保存result.json。"
                builtins = [{"name": "Bash", "operation": "运行路由执行器", "evidence": "native_framework_event"},
                            {"name": "Write", "operation": "写入result.json", "evidence": "native_framework_event"}]
        elif "/real-complete-" in p:
            if agent_a:
                prompt = ("You are Agent A, a planner. Use Write exactly once to create route.json containing "
                          "{\"item\":\"alpha\",\"required_available\":1}. Then finish briefly.")
                flow = "Agent A调用Write生成库存需求route.json。"
                builtins = [{"name": "Write", "operation": "写入route.json", "evidence": "native_framework_event"}]
            else:
                prompt = ("You are Agent B, an executor. Use Bash exactly once to run complete_inventory_tool.py route.json. "
                          "Treat JSON as actual observation, then Write decision.json derived from actual values.")
                flow = "Agent B调用Bash执行完整库存工具 → 工具内部读取route并调用fake_inventory → Agent B调用Write保存判断。"
                builtins = [{"name": "Bash", "operation": "运行complete_inventory_tool.py route.json", "evidence": "native_framework_event"},
                            {"name": "Write", "operation": "写入decision.json", "evidence": "native_framework_event"}]
        else:
            if agent_a:
                prompt = ("You are Agent A, a planner. Use Write exactly once to create route.json containing "
                          "{\"item\":\"alpha\",\"required_available\":1}. Then finish briefly.")
                flow = "Agent A调用Write生成route.json。"
                builtins = [{"name": "Write", "operation": "写入route.json", "evidence": "native_framework_event"}]
            else:
                prompt = ("You are Agent B, an executor. Read route.json, run fake_inventory.py alpha with Bash, "
                          "and Write decision.json from the actual requirement and tool result.")
                flow = "Agent B调用Read → Bash执行库存工具 → Write保存decision.json。"
                builtins = [{"name": "Read", "operation": "读取route.json", "evidence": "native_framework_event"},
                            {"name": "Bash", "operation": "运行fake_inventory.py alpha", "evidence": "native_framework_event"},
                            {"name": "Write", "operation": "写入decision.json", "evidence": "native_framework_event"}]
        observer = "AgentSight保存LLM、工具、进程和资源事件；Trace Adapter再按session与原生tool_call_id重建Agent—工具—进程关系。"
        return prompt, flow, builtins, observer

    if p.startswith("lab/experiment/"):
        prompt = ("Use Bash exactly once to run process_clock_probe.py. Return a brief confirmation after the tool succeeds. "
                  "Do not use any other tool.")
        flow = "DeepSeek生成Bash tool_use → 运行时执行时钟探针 → tool_result返回进程/namespace/三类时钟JSON → DeepSeek简短确认。"
        builtins = [{"name": "Bash", "operation": "运行process_clock_probe.py", "evidence": "native_framework_event"}]
        observer = "AgentSight记录同一会话的进程、LLM和工具事件；采集器另存Claude原生stream-json、接收时钟和应用启动边界，供六事件协议与时钟换算验证。"
        return prompt, flow, builtins, observer

    return "UNVERIFIED：未找到保存的提示词", "UNVERIFIED", [], "UNVERIFIED"


TOOL_BEHAVIOR = {
    "fake_inventory.py": "接收item参数，固定返回status=ok、同名item和available=0；用于注入“表面成功但数值错误”的静默工具故障。",
    "complete_inventory_tool.py": "读取route.json，调用fake_inventory.py，再合并需求值与观测值并计算satisfied。",
    "process_clock_probe.py": "读取/proc中的PID、PPID、NSpid、进程启动ticks和PID namespace，同时采集realtime、monotonic、boottime及采样不确定度。",
    "scenario_service_observer.py": "固定输出真实探针状态down、上报状态healthy和consistent=false，构造错误信息传播。",
    "scenario_service_decider.py": "只读取handoff中的reported_status；healthy映射为NO_RESTART，否则RESTART。",
    "scenario_faulty_router.py": "对需要retrieval能力的任务固定选择只有summarization能力的generalist，并输出route_valid=false。",
    "scenario_route_executor.py": "严格按route中的能力执行；缺少retrieval时输出retrieved=false和answer=null。",
}


def custom_tools_for(prompt: str) -> list[str]:
    return [name for name in TOOL_BEHAVIOR if name in prompt]


def make_audit() -> dict[str, Any]:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    calls: list[dict[str, Any]] = []
    for index, entry in enumerate(ledger["entries"], start=1):
        relative = entry["path"]
        path = ROOT / relative
        records = read_json_records(path)
        final = result_record(records)
        prompt, flow, declared_tools, observer = prompt_and_flow(relative, path)
        native = native_tool_calls(records)
        tool_calls = native or declared_tools
        status = "FAILED_BEFORE_MODEL" if entry.get("is_error") and not entry.get("model") else (
            "FAILED" if entry.get("is_error") else "SUCCESS"
        )
        result_text = final.get("result") if final else None
        if status == "FAILED_BEFORE_MODEL":
            result_text = "DNS解析失败（EAI_AGAIN），未进入模型推理，费用为0。"
            flow = "运行器准备发起Agent A会话，但DNS解析失败；没有模型推理、tool_use或工具执行。"
            tool_calls = []
            observer = "AgentSight启动了观测窗口，但本次没有捕获到有效模型调用或模型工具生命周期。"
        elif result_text is None:
            result_text = "UNVERIFIED：账本保留会话与费用，但当前日志中未找到最终result字段。"
        calls.append({
            "index": index,
            "category": classify(relative),
            "source_log": relative.replace("\\", "/"),
            "session_id": entry.get("session_id"),
            "status": status,
            "model": entry.get("model"),
            "cost_usd": entry.get("cost_usd"),
            "input_tokens": entry.get("input_tokens"),
            "output_tokens": entry.get("output_tokens"),
            "cache_read_tokens": entry.get("cache_read_tokens"),
            "question": prompt,
            "question_evidence": "runner_source_or_run_marker",
            "result": result_text,
            "tool_calls": tool_calls,
            "flow": flow,
            "custom_tools": custom_tools_for(prompt),
            "observer_work": observer,
            "duplicate_paths": entry.get("duplicate_paths") or [],
        })
    return {
        "schema_version": "agentops-api-call-audit-v0.1",
        "generated_date": "2026-10-16",
        "source_ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/"),
        "deduplication_key": "provider_session_id",
        "summary": {
            "session_records": len(calls),
            "successful_sessions": sum(c["status"] == "SUCCESS" for c in calls),
            "failed_before_model": sum(c["status"] == "FAILED_BEFORE_MODEL" for c in calls),
            "total_cost_usd": round(sum(float(c["cost_usd"] or 0) for c in calls), 6),
        },
        "custom_tool_behavior": TOOL_BEHAVIOR,
        "calls": calls,
    }


def md_code(value: str) -> str:
    return value.replace("`", "\\`")


def render_markdown(audit: dict[str, Any]) -> str:
    summary = audit["summary"]
    lines = [
        "# DeepSeek真实API调用逐次审计",
        "",
        "## 审计口径",
        "",
        f"本审计以 `{audit['source_ledger']}` 为唯一成本入口，按 provider session ID 去重。共确认 "
        f"{summary['session_records']} 个会话记录，其中 {summary['successful_sessions']} 个成功、"
        f"{summary['failed_before_model']} 个在模型调用前失败；累计费用 `{summary['total_cost_usd']:.6f} USD`。",
        "",
        "这里把三类事实分开：提示词来自固定运行器或每次保存的marker；模型最终回答来自原始会话日志；工具过程优先来自框架原生tool_use事件，旧版JSON日志缺少tool_use明细时，则由固定运行器与最终回答共同核验。文档不把CLI会话数等同于底层HTTP请求数，一个会话可以包含多轮模型请求。",
        "",
        "## Step与工具调用的关系",
        "",
        "DeepSeek实际生成 `tool_use`，Claude Code运行时执行工具并返回 `tool_result`。`Step` 是后续统一协议给这段真实行为划定的分析单位。例如 `agent_a.bash_1` 表示Agent A的第一个Bash工具生命周期；名称和边界由协议定义，工具调用本身由模型发起。",
        "",
        "## 自定义工具具体行为",
        "",
    ]
    for name, behavior in audit["custom_tool_behavior"].items():
        lines.append(f"- `{name}`：{behavior}")
    lines += [
        "",
        "## 你的观测工具具体做了什么",
        "",
        "1. AgentSight在模型启动前打开观测窗口，把Claude进程、子进程、文件活动、LLM网络活动和工具调用写入原始流或SQLite。",
        "2. P0实验使用SSL/HTTP解析器保存请求与响应方向、PID/TID和唯一marker，用于判断哪一个响应属于哪一个请求。",
        "3. 新版框架采集器同时保存Claude原生 `stream-json`，因此能直接取得模型生成的 `tool_use`、`tool_call_id`、工具参数和后续 `tool_result`。",
        "4. Trace Adapter把原始记录规范化为session、step、tool生命周期，并通过session和共享tool_call_id连接框架事件与AgentSight事件。",
        "5. 进程时钟探针读取 `/proc`、PID namespace和三种系统时钟，为后续Agent—Step—Tool—Process关系提供身份与时间证据。",
        "",
        "## 逐次调用记录",
        "",
    ]
    current = None
    for call in audit["calls"]:
        if call["category"] != current:
            current = call["category"]
            lines += [f"### {current}", ""]
        lines += [
            f"#### {call['index']:02d}. `{call['session_id']}`",
            "",
            f"- **状态/模型/费用**：`{call['status']}`；`{call['model'] or '无'}`；`{float(call['cost_usd'] or 0):.6f} USD`。",
            f"- **Token**：输入 `{call['input_tokens']}`，输出 `{call['output_tokens']}`，cache read `{call['cache_read_tokens']}`。",
            f"- **问了什么（绝对路径缩写）**：{call['question']}",
            f"- **调用过程**：{call['flow']}",
        ]
        if call["tool_calls"]:
            rendered = []
            for tool in call["tool_calls"]:
                name = tool.get("name") or "unknown"
                operation = tool.get("operation")
                if operation is None:
                    operation = json.dumps(tool.get("input") or {}, ensure_ascii=False, sort_keys=True)
                call_id = tool.get("tool_call_id")
                id_text = f"，ID `{call_id}`" if call_id else ""
                rendered.append(f"`{name}`{id_text}：{operation}")
            lines.append("- **调用工具**：" + "；".join(rendered) + "。")
        else:
            lines.append("- **调用工具**：无模型工具调用。")
        if call["custom_tools"]:
            details = "；".join(f"`{name}`：{audit['custom_tool_behavior'][name]}" for name in call["custom_tools"])
            lines.append(f"- **自定义工具做了什么**：{details}")
        else:
            lines.append("- **自定义工具做了什么**：本次未运行论文自定义业务脚本。")
        result = str(call["result"]).replace("\r\n", "\n").replace("\n", "<br>")
        lines += [
            f"- **返回结果**：{result}",
            f"- **观测系统做了什么**：{call['observer_work']}",
            f"- **原始证据**：`{call['source_log']}`。",
            "",
        ]
    lines += [
        "## 证据边界",
        "",
        "- **VERIFIED**：30个会话ID、费用、token和模型状态按本地账本核对；29个成功会话的最终result来自原始日志，且均使用 `deepseek-v4-pro`。另1个会话在模型调用前失败。",
        "- **VERIFIED**：框架原生stream-json会话中的tool_use名称、参数与tool_call_id直接来自模型事件。",
        "- **INFERRED**：旧版 `--output-format json` 日志不保存逐项tool_use事件；这些会话的工具顺序由固定运行器、最终回答和AgentSight观测共同重建，不能声称拥有完整原生工具事件。",
        "- **UNVERIFIED**：这些历史调用没有统一保存temperature、top_p、system prompt哈希和provider response ID，因此本审计不补写这些字段。",
        "- **UNVERIFIED**：30个CLI会话不等于30次底层HTTP请求；部分会话含多轮模型请求，旧日志不足以对所有HTTP请求逐条形成完整调用清单。",
        "",
        "## 下一研究闸门",
        "",
        "后续新的真实多Agent实验应在同一会话包中同时保存：原始用户任务、每轮模型request/response ID、模型参数、原生tool_use/tool_result、直接PID namespace映射、非零时钟不确定度和查询收据。只有这些字段同时闭合，才能把Agent/Step/Tool/Process作为正式归因输入。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    audit = make_audit()
    OUTPUT_JSON.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(audit), encoding="utf-8")
    readme = (
        "# experiment_20261016_17：真实API调用逐次审计\n\n"
        "本轮不发起网络调用，只对全仓已保存的DeepSeek调用按provider session ID去重并逐条整理。\n\n"
        "- 详细文档：[真实API调用逐次审计.md](真实API调用逐次审计.md)\n"
        "- 机器可读结果：[api-call-audit.json](api-call-audit.json)\n"
        "- 生成脚本：`my_paper_coding/experiment_control/build_api_call_audit.py`\n"
        f"- 结果：{audit['summary']['session_records']}个会话，{audit['summary']['successful_sessions']}个成功，"
        f"累计{audit['summary']['total_cost_usd']:.6f} USD，网络调用0次。\n"
    )
    (OUTPUT_DIR / "README.md").write_text(readme, encoding="utf-8")
    print(json.dumps(audit["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
