# AgentSight attach-mode 真实观测结果

**版本**：v0.1
**运行时间**：2026-09-28
**运行目录**：`results/agentsight-attach-20260928/`

## 结果

这次运行采用 AgentSight 在 WSL2 下的 attach 模式：先执行 `record -c claude`，再启动 Claude。Claude 只调用一次 Bash，运行本地 `fake_inventory.py alpha`，工具返回 `available=0`，而任务要求 `available=1`。

| 检查项 | 结果 |
|---|---:|
| Agent 退出码 | 0 |
| `process_nodes` | 43 |
| `audit_events` | 97 |
| `llm_calls` | 2 |
| `token_usage` | 2 |
| `tool_calls` | 1 |
| `network_targets` | 2 |
| `resource_samples` | 27 |
| `files` | 6 |

数据库行数来自 `db-rows.txt`，原始过程证据来自 `raw-stream.log`。原始流中可以找到 Claude 的 `EXEC`、`python3 fake_inventory.py alpha`、Python 进程退出和文件打开事件；`claude-run.log` 中的最终结果明确指出 `available=0` 不满足 `available=1`。

## 问题修复

此前用 `agentsight record -- python3 ...` 属于 launch 模式。当前 WSL2 环境下该模式会出现目标进程成功但数据库为 0 的归因丢失。改用 `record -c claude` 后，LLM、工具、进程、文件和网络事件均进入 SQLite session。

## 证据边界

- **VERIFIED**：attach 模式解决了本机 WSL2 的 0 事件问题；真实 Claude 运行产生了非零观测数据。
- **VERIFIED**：受控工具错误的观察值为 `available=0`，最终任务判断为失败。
- **UNVERIFIED**：仅凭本次单 Agent 运行不能证明跨 Agent 责任归因；还需要多 Agent 结构和独立的 Agent/Step/Edge 真值。
- **AUTHOR_INPUT_NEEDED**：后续多 Agent 任务中各角色的责任标签协议。
