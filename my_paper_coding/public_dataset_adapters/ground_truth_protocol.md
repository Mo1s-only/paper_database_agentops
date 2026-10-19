# 统一归因真值协议 v0.1

本协议只规范归因评测输入，不运行归因算法。一个记录对应一次 `run/session`，并按 `agent → step/span → relation` 保存结构。

## 五类真值

1. `responsibility_agents`：对任务失败负决定性责任的 Agent。
2. `responsibility_steps`：决定性错误步骤；仅有一般错误位置时必须标为 `partial`。
3. `root_cause_nodes`：执行图中的根因节点。
4. `propagation_edges`：错误从一个节点传播到另一个节点的有向边。
5. `causal_paths`：从根因节点到失败表现节点的有序完整路径。

## 状态

- `direct`：源数据直接标注该对象。
- `derived`：通过无歧义、可重放的字段映射获得，例如由已标注根因节点查得其 Agent。
- `partial`：源数据只标注了相邻概念，不能提升为完整责任结论。例如 TRAIL 的错误 span 是错误位置，不自动等于决定性根因步骤。
- `abstain`：源数据不足以确认该类真值。不得用顺序邻接、文本相似度或模型猜测补齐。

每个非 `abstain` 标签必须至少绑定一条 evidence，包含源文件、JSON Pointer、源记录 SHA-256、直接/派生类型和映射方法。`abstain` 必须说明缺失原因且 values/evidence 为空。

## 三个数据集的保守映射

| 数据集 | Agent | Step/span | Relation | 五类真值边界 |
|---|---|---|---|---|
| Who&When | history.name、system_prompt 键 | history 数组索引 | 相邻日志仅重建为 temporal relation | 责任 Agent/Step 为直接标注；根因节点由决定性步骤无歧义派生；边和路径 abstain |
| TRAIL | span.service_name | OpenTelemetry span_id | parent_span_id/child_spans | 错误 span 只作为 partial responsibility step；根因、责任 Agent、传播边和路径 abstain |
| AgentTrace | node.agent_id | 图节点 id 与 data.step | 原始 edges | 根因节点和路径为直接标注；责任 Agent/Step及路径边由图无歧义派生 |

## 兼容性指标

- 字段覆盖率：记录中 run/session、Agent、Step、Relation 是否非空。
- 关系重建率：成功转换的源关系数 / 源数据中可识别的关系机会数。
- 证据完整率：Step、Relation 和非 abstain 真值中具有合法源指针的对象数 / 对象总数。
- 拒绝率：五类真值中 `abstain` 槽位数 / 全部真值槽位数。
- 标签覆盖率：每一种真值在多少记录中达到 direct、derived 或 partial。

这些指标只回答“当前协议能否无损、诚实地承载公开数据”，不代表归因算法准确率。
