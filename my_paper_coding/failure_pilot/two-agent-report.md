# 两 Agent AgentSight 观测结果

**版本**：v0.1
**时间**：2026-09-28
**运行目录**：`results/agentsight-two-agent-20260928/`

## 运行设计

- Agent A 只负责写入 `route.json`，表示 `alpha` 需要 `available=1`；
- Agent B 读取 `route.json`，调用本地 `fake_inventory.py`，再写入 `decision.json`；
- 假工具返回格式合法但错误的 `available=0`；
- `ground_truth.json` 单独保存责任 Agent B、责任步骤和任务要求。

两次 Claude 调用由同一个 `agentsight record -c claude` attach session 监控，避免 launch 模式在 WSL2 下丢失进程归因。

## 证据要求

本报告对应的结果目录生成后，应检查：

1. `agent-a-exit.txt` 和 `agent-b-exit.txt` 均为 0；
2. `route.json`、`decision.json` 均存在；
3. `db-rows.txt` 中 `process_nodes`、`llm_calls`、`tool_calls` 为非零；
4. `raw-stream.log` 中出现两个 Claude 进程以及 `fake_inventory.py alpha`；
5. `ground_truth.json` 与 Agent B 的最终决策可离线比对。

这一步只验证多 Agent 观测链是否可用。责任 Edge 的论文级评测仍需把 AgentSight 事件归一化到统一 `trace.jsonl`，并加入多次重复和独立标签。

## 本次运行结果

运行目录 `results/agentsight-two-agent-20260928/` 中两个 Agent 的退出码均为 0，两个中间文件均生成。AgentSight SQLite 记录：

| 证据表 | 数量 |
|---|---:|
| `process_nodes` | 53 |
| `audit_events` | 119 |
| `llm_calls` | 6 |
| `token_usage` | 6 |
| `tool_calls` | 4 |
| `network_targets` | 4 |
| `resource_samples` | 49 |

`raw-stream.log` 能定位到 Agent A 和 Agent B 两个 Claude 进程，以及 Agent B 执行 `fake_inventory.py alpha` 的 Python 子进程。这个结果已经解决了“真实多 Agent 运行没有进入 AgentSight 数据库”的问题，但责任 Edge 仍需由统一化适配器从原始事件中计算，不能直接把本次观察数量当作归因准确率。

## 统一化与归因试跑

`normalize_two_agent_probe.py` 已将本次 AgentSight 原始流、工作区文件和真值清单转换为 7 个事件的 `trace.jsonl`，并记录了 Agent A/B 的观测 PID 和假工具 PID。随后调用 `analyze_failure_pilot.py`：

- Agent 精确匹配：`true`；
- Step 精确匹配：`true`；
- Edge 精确匹配：`true`；
- 证据区间召回率：`1.0`。

这仍是单次、确定性、同一 harness 生成真值的试跑，结论等级保持为 `VERIFIED_FOR_THIS_SYNTHETIC_PILOT`。
