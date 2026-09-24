# 第 3 章：单 Agent 核心机制

本章正文：[详细教程](详细教程.md)；学习后完成：[练习与验收](练习与验收.md)；最后对照：[练习与验收答案](练习与验收答案.md)。

## 本章定位

先把 Agent 看成一个带状态的闭环执行系统，再讨论框架或模型。统一抽象有助于跨 LangGraph、AutoGen、CrewAI、Claude Code 等具体实现比较 trace。

## 统一抽象

```text
目标/约束
   ↓
感知当前状态 → 选择下一动作 → 调用模型或工具 → 观察结果 → 更新状态
      ↑                                                   ↓
      └────────────── 停止、重试、反思或继续 ────────────┘
```

一个 Agent 运行至少可以分为：

- `run`：一次端到端任务；
- `agent`：承担角色和策略的执行主体；
- `step`：一次可解释的状态转移；
- `model_call`：一次模型请求—响应；
- `tool_call`：一次工具请求—结果；
- `observation`：环境反馈；
- `outcome`：任务结果和约束满足情况。

## 学习目标

- 区分工作流与自主 Agent。
- 理解 ReAct 式“推理/动作/观察”循环、planner–executor、router 和 state machine。
- 理解短期上下文、长期记忆、外部知识库和运行状态。
- 理解停止条件、预算、重试、回退、人工介入和反思。
- 能把具体框架映射到统一事件模型。

## 关键辨析

### 计划不等于执行

模型声明要调用工具，只是意图；工具真实执行并产生副作用，才是系统事实。

### 记忆不等于上下文

上下文是当前调用可见输入；记忆是可跨步骤或运行保存、检索和更新的信息机制。记忆错误可能来自写入、检索、排序、污染或过期。

### 反思不等于验证

让同一模型“再想一遍”是自我评价；可执行测试、独立观测或外部真值才更接近验证。

## 项目内材料

- [AgentSight 论文精读笔记](../../Reference paper/01_agent_observation/AgentSight_论文精读笔记.md)
- [Agent session](../../lab/agentsight/docs/agent-session.md)
- [Session-centric top](../../lab/agentsight/docs/design/session-centric-top.md)
- [Operation tree](../../lab/agentsight/docs/design/vis/operation-tree.md)
- [Intent-to-effect flame graph](../../lab/agentsight/docs/design/vis/intent-to-effect-flame-graph.md)

## 本章完成标准

选择一个真实 Agent 任务，画出状态机和 operation tree；每个节点必须能映射到可观察事件或明确标为不可观察。
