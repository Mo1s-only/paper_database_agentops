# 第 7 章：AgentOps 可观测性与追踪

本章正文：[详细教程](详细教程.md)；学习后完成：[练习与验收](练习与验收.md)；最后对照：[练习与验收答案](练习与验收答案.md)。

## 本章定位

AgentOps 关注 Agent 从开发、部署到运行和改进的可观测、可评价、可治理过程。本项目首先研究的是：怎样把模型语义活动与系统实际行为组织成可审计证据。

## 学习目标

- 区分日志、指标、追踪、事件、Span、会话和快照。
- 理解应用插桩、代理/网关、原生日志和系统边界追踪的差别。
- 理解 OpenTelemetry 的 trace/span/context/attribute 基本模型。
- 理解 eBPF 的观测位置、优势、权限和语义局限。
- 能设计跨框架统一事件 schema 和关联策略。
- 理解可观测性成本、采样、隐私与证据完整性的权衡。

## 三层观测模型

| 层 | 看什么 | 优势 | 盲点 |
|---|---|---|---|
| 应用/语义层 | Agent、步骤、消息、工具语义 | 语义强、易解释 | 依赖框架插桩，可能遗漏真实副作用 |
| 传输/边界层 | HTTP/TLS、stdio、文件、进程 | 跨框架、接近实际行为 | 关联和解析困难，可能含敏感数据 |
| 认知/推断层 | 隐式推理的重建或解释 | 辅助理解决策偏差 | 不是模型内部真值，存在忠实性风险 |

## 最小统一事件 schema

```text
run_id, event_id, parent_event_id
agent_id, step_id, event_type
timestamp_start, timestamp_end, clock_domain
source_layer, source_process, source_host
input_ref, output_ref, status, error_type
tool/model/resource metadata
confidence, completeness, redaction
```

主键必须稳定；原始载荷与摘要最好分离；无法确认的关联应保留候选和置信度，不能强行唯一配对。

## 关键研究问题

- 哪些观测信号对归因真正有增益？
- 证据缺失到什么程度会使归因失效？
- 全量记录与自适应采样如何权衡成本和隐私？
- 跨框架事件能否映射到同一执行图？

## 项目内材料

- [AgentOps 精读笔记](../../Reference paper/01_agent_observation/AgentOps_论文精读笔记.md)
- [AgentSight 精读笔记](../../Reference paper/01_agent_observation/AgentSight_论文精读笔记.md)
- [OTel 说明](../../lab/agentsight/docs/otel.md)
- [OpenTelemetry 设置](../../lab/agentsight/docs/design/opentelemetry_setup.md)
- [Snapshot schema](../../lab/agentsight/docs/snapshot-schema.md)
- [AgentSight 输出数据说明](../../lab/agentsight/results/AgentSight输出数据说明.md)
- [产品范围：Agent-native](../../lab/agentsight/docs/design/product-scope-agent-native.md)

## 本章完成标准

能为一次 Agent 运行定义事件 schema，说明每个字段的采集层、关联键、缺失风险、隐私风险和论文用途。
