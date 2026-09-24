# 第 8 章：因果归因与根因诊断

本章正文：[详细教程](详细教程.md)；学习后完成：[练习与验收](练习与验收.md)；最后对照：[练习与验收答案](练习与验收答案.md)。

## 本章定位

观测回答“发生了什么”，归因回答“谁/哪一步对失败负责”，诊断回答“为什么失败以及如何验证”。本章是论文主线的核心方法层。

## 学习目标

- 区分相关、时序先后、依赖、贡献、责任和因果。
- 掌握 Agent、Step、Tool、Message、Edge 五种责任粒度。
- 理解执行图、错误依赖图、因果图和证据图的差别。
- 理解干预、反事实、局部重放、删除测试和替换测试。
- 设计带置信度、证据区间和可验证动作的诊断报告。

## 归因对象

| 粒度 | 问题 | 优点 | 风险 |
|---|---|---|---|
| Agent | 哪个角色主要导致失败？ | 易解释 | 太粗，无法修复 |
| Step | 何时首次产生决定性错误？ | 可定位 | 长轨迹困难 |
| Tool/Call | 哪次调用异常？ | 可执行验证 | 不能覆盖纯语义错误 |
| Message | 哪条信息污染后续？ | 支持传播分析 | 信息被复制/改写时难追踪 |
| Edge | 哪个依赖或传播关系传递了错误？ | 适合跨层因果链 | 真值构造最难 |

## 推荐诊断管线

```text
任务失败判定
→ 执行图重建
→ 异常候选生成
→ 责任候选排序
→ 局部反事实/重放验证
→ 根因类型与证据链报告
```

反事实要明确“改变什么、保持什么不变、重新执行到哪里、以什么判据认定任务恢复”。只问 LLM“如果没有这一步会怎样”不等于执行了反事实。

## 多因果与责任

可能存在多个充分原因、多个必要原因或触发—传播—暴露链。标注协议应允许：主责任、共同责任、上游触发、传播节点、检测节点和不确定状态。

## 项目内材料

- [Which Agent 精读笔记](../../Reference paper/02_failure_attribution/WhichAgentCausesTaskFailures_论文精读笔记.md)
- `Reference paper/02_failure_attribution/EDGE_Error_Dependency_Graph_text.txt`
- `Reference paper/02_failure_attribution/CDC-MAS_Automatic_Failure_Attribution_text.txt`
- `Reference paper/02_failure_attribution/TraceElephant_Seeing_the_Whole_Elephant_text.txt`
- [AgentTrace 提取文本](../../Reference paper/01_agent_observation/AgentTrace_Causal_Graph_Tracing_text.txt)
- [因果时间线](../../lab/agentsight/docs/design/vis/causal-timeline.md)
- [方向 01 方法框架](../../my_paper/方向框架/01_跨层因果边归因与可验证诊断/02_方法与系统框架.md)

## 本章完成标准

对一条失败 trace 生成可复核的候选排名；每个候选含证据、竞争解释、置信度和反事实验证计划，且不把时序相邻直接写成因果。
