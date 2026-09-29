# 真实 Trace Adapter 链路 Canary 报告

**版本**：v0.1
**时间**：2026-09-29
**状态**：`VERIFIED_FOR_REAL_API_AND_AGENTSIGHT_CAPTURE`

## 运行目录

`results/real-canary-20260929-ubuntu24/`

本次运行使用 Ubuntu 24.04、AgentSight 1.0.31、Claude Code CLI 和已有的 DeepSeek Anthropic-compatible endpoint。没有使用 synthetic trace 代替真实观测。

## 真实调用结果

| 项目 | 结果 |
|---|---:|
| Agent A 退出码 | 0 |
| Agent B 退出码 | 0 |
| 应用层结果记录 | 2 |
| AgentSight `llm_calls` | 6 |
| AgentSight `tool_calls` | 4 |
| AgentSight `audit_events` | 113 |
| AgentSight `process_nodes` | 51 |
| AgentSight `resource_samples` | 36 |
| AgentSight 数据库总表行 | 220 |
| 本次 API 成本 | 0.217746 USD |

Agent A 创建 `route.json`；Agent B 读取路由、执行 Bash 工具、读取 `available=0`，并写入 `decision.json`。

## Adapter 链路检查

运行：

```powershell
python .\my_paper_coding\trace_adapter\build_run_index.py
python .\my_paper_coding\trace_adapter\normalize_runs.py
python .\my_paper_coding\trace_adapter\smoke_check.py `
  .\my_paper_coding\failure_pilot\results\real-canary-20260929-ubuntu24 `
  --normalized .\my_paper_coding\trace_adapter\structured_runs\normalized\failure_pilot\real-canary-20260929-ubuntu24\evidence-events.jsonl
```

规范化结果包含 220 条 AgentSight SQLite 观测记录和 2 条应用层最终结果记录。每条记录带原始文件、表名或行号引用。`route.json`、`decision.json` 和独立 `ground_truth.json` 均存在。

## 证据边界

- **VERIFIED**：真实 API 调用、真实 AgentSight SQLite 观测、应用最终结果、任务工件和证据级规范化均完成。
- **UNVERIFIED**：跨层 session/PID/工具调用自动对齐、自动生成统一 trace、责任边和归因准确率。
- **限制**：当前 Claude 日志仍是最终结果 JSON，不是完整 Agent step/tool JSONL；smoke check 不生成责任标签。

第一次尝试使用默认 Ubuntu 20.04 时，AgentSight 因 glibc 2.31 低于所需版本而启动失败；该运行保留在 `results/real-canary-20260929/`，应用调用成功但不计入 AgentSight 观测成功样本。采集脚本已经加入启动失败和空数据库检查，避免再次出现假通过。
