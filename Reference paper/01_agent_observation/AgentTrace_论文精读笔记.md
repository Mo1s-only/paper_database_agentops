# AgentTrace 论文精读笔记

## 论文信息

- 标题：AgentTrace: Causal Graph Tracing for Root Cause Analysis in Deployed Multi-Agent Systems
- 作者：Zhaohui Geoffrey Wang
- Venue/年份：ICLR 2026 Agents in the Wild Workshop
- 官方来源：[OpenReview PDF](https://openreview.net/pdf?id=22qiB2JpzZ)
- 本地论文：`AgentTrace_Causal_Graph_Tracing.pdf`
- 阅读目的：日志到因果图、可解释候选排序
- 状态：精读；发表状态 `VERIFIED`（Workshop）

## 1. One-sentence contribution

AgentTrace 从多 Agent 执行日志重建包含顺序、通信和数据依赖的图，从失败表现向后搜索候选根因，并用结构和位置特征进行低延迟排序。

## 2. Problem setting

论文针对部署后的多 Agent 工作流，假设系统保存了结构化或半结构化执行日志。失败可能通过多次消息传递和工具调用传播，最后才表现为错误答案或异常，因此直接看最后一个错误节点会混淆症状和根因。

## 3. Method core

方法包括日志解析、节点和边构造、从失败节点进行 backward tracing，以及基于结构位置、路径长度、内容和流信息的候选排序。设计目标是调试时不再调用 LLM，以获得可解释和低延迟的定位结果。它把因果图作为运行后分析的中间表示。

## 4. Evidence

论文报告在多类多 Agent 故障场景上进行评估，并与启发式和 LLM-based baseline 比较，强调较高的定位准确率和亚秒级延迟。具体数据规模、标签构造和泛化边界应以论文正文和附录为准，不能仅依据摘要中的“diverse benchmark”扩大解读。

## 5. Limitations

该方法依赖日志中已有的 Agent、消息和数据依赖信息；若 AgentSight 只看到进程或 syscall，必须先完成语义适配。图边方向本身主要表示可观察依赖，不自动等于责任因果。Workshop 论文的评估规模和正式级别也低于 ICML/ACL/NeurIPS 主会基准。

## 6. Use for my thesis

AgentTrace 是你的规则图基线，而不是可以忽略的相关工作。你的差异应放在：系统级 eBPF 事件如何补齐应用日志缺失、每条边如何附 provenance/confidence、以及如何用最小反事实干预验证边级责任。实验中应包含 AgentTrace-style graph-only baseline。

## 7. Claim–evidence rows

| Claim | Evidence | Status |
|---|---|---|
| 执行日志可以重建多 Agent 因果图 | 论文方法与摘要 | `VERIFIED` |
| 反向搜索可作为低成本候选生成器 | 方法部分 | `VERIFIED` |
| 观察图中的边就是决定性责任边 | 论文未充分证明 | `UNVERIFIED` |
