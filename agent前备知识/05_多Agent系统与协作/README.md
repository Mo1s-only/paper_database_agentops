# 第 5 章：多 Agent 系统与协作

本章正文：[详细教程](详细教程.md)；学习后完成：[练习与验收](练习与验收.md)；最后对照：[练习与验收答案](练习与验收答案.md)。

## 本章定位

多 Agent 系统不是“把模型调用次数变多”，而是多个带角色、状态和权限的执行主体通过通信与环境发生耦合。论文中的故障传播、责任分配和拓扑干预都依赖这一层。

## 学习目标

- 理解角色分工、能力异质性和责任边界。
- 掌握 pipeline、supervisor、router、debate、peer-to-peer、blackboard/shared-workspace 等拓扑。
- 理解消息协议、handoff、共享状态、同步和冲突解决。
- 区分通信边、依赖边、控制边和因果边。
- 理解关键路径、瓶颈、冗余、掉队、死锁和错误放大。

## 分析一个 MAS 的六个问题

1. **谁**：有哪些 Agent，角色、模型、工具和权限是什么？
2. **何时**：步骤是顺序、并行、循环还是事件驱动？
3. **说什么**：消息内容、格式、置信度和版本如何表示？
4. **依赖谁**：哪个输出是哪个后续决策的必要输入？
5. **写哪里**：状态是私有、共享、外部数据库还是工作区文件？
6. **谁负责**：最终决策、验证、回滚与人工升级由谁承担？

## 常见失败

- 角色或任务分配错误；
- 信息丢失、截断、过期或错误传播；
- supervisor 成为单点瓶颈；
- 并发修改共享状态导致冲突；
- Agent 互相等待、重复工作或循环争论；
- 弱 Agent 的错误被高信任地转发；
- 最终聚合器掩盖中间失败。

## 项目内材料

- [多 Agent 协调案例](../../lab/agentsight/docs/experiment/case-study/multi-agent-coordination/README.md)
- [Subagent 使用模式](../../lab/agentsight/docs/experiment/case-study/multi-agent-coordination/subagent-usage-patterns.md)
- [多 Agent 因果图](../../lab/agentsight/docs/design/vis/multi-agent-causal-map.md)
- [AgentDropout 精读笔记](../../Reference paper/04_prediction_early_warning/AgentDropout_论文精读笔记.md)
- `Reference paper/01_agent_observation/Understanding the Information.pdf`
- [文献总索引](../../Reference paper/literature_index.md)

## 本章完成标准

能为一个 MAS 画出角色图、通信图、共享状态图和关键路径，并解释拓扑如何改变成本、性能和错误传播。
