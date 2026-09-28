# 受控失败归因 Pilot 报告

**版本**：v0.1
**时间**：2026-09-28
**状态**：`VERIFIED_FOR_THIS_SYNTHETIC_PILOT`

## 目的

验证方向 01 所需的最小闭环是否可以被明确表示：统一观测轨迹、独立责任真值、责任 Agent、责任 Step、责任 Edge，以及从局部证据到最终失败的证据区间。

## 实验设置

实验完全由 Python 标准库生成，不访问网络，也不依赖模型 API。两 Agent 完成一次库存检查：Agent A 负责规划和汇总，Agent B 负责查询工具。伪工具返回格式合法的 `status=ok`，但把应为 `available=1` 的结果返回为 `available=0`。最终任务失败。

观测轨迹包含 8 个事件，真值单独保存到 `ground_truth.json`，轨迹中没有 `fault_injected` 标签。这样可以先测试“从证据推断责任”，而不是直接读取故障标签。

## 运行结果

| 项目 | 结果 |
|---|---|
| 轨迹事件数 | 8 |
| 预测责任 Agent | `agent_b` |
| 真值责任 Agent | `agent_b` |
| 预测责任 Step | `agent_b.tool_call` |
| 真值责任 Step | `agent_b.tool_call` |
| 预测责任 Edge | `evt-004 → evt-005` |
| 真值责任 Edge | `evt-004 → evt-005` |
| Agent 精确匹配 | 1.0 |
| Step 精确匹配 | 1.0 |
| Edge 精确匹配 | 1.0 |
| 证据区间召回 | 1.0 |

输出文件位于 `results/pilot-01/`：

- `trace.jsonl`：统一事件轨迹；
- `ground_truth.json`：独立责任真值；
- `analysis.json`：推断、基线和比对结果；
- `run-meta.json`：运行元数据。

## 基线对照

- B0 只看最终输出：能判断任务失败，无法定位 Agent 或 Step。
- B1 只看消息日志：可把候选缩小到 Agent A / Agent B，但不能确定责任 Step。
- B2 加入工具证据：在本 pilot 中得到唯一候选，并与责任 Edge 真值一致。

这只是一个可执行的构造性对照，不是跨任务性能结论。

## AgentSight 观测链探针

在挂载 WSL tracefs 后，用 AgentSight 记录同一个无网络 Python 工作流，得到一份本地 SQLite session。该 session 正常结束，但报告为 `0 API calls · 0 tokens · 0 execs · 0 files · 0 network endpoints`，audit 也为空。

这说明当前工作流的统一真值层可以独立运行，而 AgentSight 的 LLM/系统观测层不会自动把 Python 内存中的合成事件转换成模型调用或工具事件。这个结果是 **VERIFIED** 的边界观察，不应被解读为 AgentSight 失效。下一步要把真实 AgentSight 事件与本 pilot 的责任真值放在同一任务中，而不是只记录一个脱离 AgentSight 的合成脚本。

## 证据等级与局限

- **VERIFIED**：脚本可重复运行；轨迹、真值和分析文件生成成功；本次合成故障的 Agent、Step、Edge 均精确匹配。
- **INFERRED**：工具证据有望成为跨层归因的关键增量，但仍需在 AgentSight 真实事件上验证。
- **UNVERIFIED**：并发调用、重试、循环、多个同时异常、真实 API 错误和不同 Agent 架构下的泛化能力。
- **AUTHOR_INPUT_NEEDED**：后续真实失败任务的标签协议，以及哪些故障由人工确认、哪些由可执行反事实确认。

## 下一道研究门

把 `trace.jsonl` 的统一字段映射到 AgentSight 的进程、网络、工具和模型调用事件，再设计至少三类故障（静默工具错误、错误传播、路由/角色错误），每类重复运行并用独立真值评测 B0/B1/B2/B3。达到 30–50 条带真值失败 trace 后，才能讨论方法差异和统计区间。
