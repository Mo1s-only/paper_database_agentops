# TraceElephant 论文精读笔记

## 论文信息

- 标题：Seeing the Whole Elephant: A Benchmark for Failure Attribution in LLM-based Multi-Agent Systems
- 作者：Mengzhuo Chen 等
- Venue/年份：ACL 2026 Long Paper
- 官方来源：[ACL Anthology](https://aclanthology.org/2026.acl-long.912/)
- 本地论文：`TraceElephant_Seeing_the_Whole_Elephant.pdf`
- 阅读目的：故障归因基准、完整可观测性、动态重放
- 状态：精读；发表状态 `VERIFIED`

## 1. One-sentence contribution

TraceElephant 将多 Agent 故障归因定义在完整执行轨迹和可复现实验环境上，并提供 380 条轨迹（220 条失败）来研究完整观测、静态分析和动态重放对 Agent/Step 归因的影响。

## 2. Problem setting

论文研究开发者面对的失败归因问题：给定任务失败、完整执行过程和系统配置，识别负责的功能组件/Agent 以及失败变得不可恢复的决定性步骤。这里的组件不一定是独立 Agent，也可以是规划、编排或工具使用模块。论文特别强调，早期错误如果仍可被后续验证器修复，就不应直接标成根因。

## 3. Method core

TraceElephant 的核心是基准构造而不是一个新的归因模型。每个实例包含任务、系统配置、Agent roster、工具、完整步骤级输入输出、系统结构以及可执行代码。论文比较静态归因和动态归因：静态方法直接阅读完整 trace；动态方法先生成候选，再从相关执行点重放，并用反事实结果确认候选。该定义把“最早错误”与“决定性错误”区分开来。

## 4. Evidence

- 覆盖 Captain-Agent、Magentic-One、SWE-Agent 三类系统，以及 GAIA、AssistantBench、SWE-Bench 任务。
- 总计 380 条执行轨迹，其中 220 条失败。
- 完整观测平均达到 65.9% Agent-level、30.3% Step-level 准确率；相对 output-only 设置，Step-level 提升约 76%，动态重放还可继续提升。
- 论文通过去掉输入、metadata、工具上下文等消融，展示细粒度步骤定位比 Agent 级定位更依赖完整上下文。

证据位置：摘要、§2 Problem Definition、§3.1 Table 1、§4 Experiments、§5 Analysis。

## 5. Limitations

论文主要依赖 turn-based、单步选择一个组件的执行协议，并要求保存可执行环境。并发、异步 Agent 和无法重放的外部服务尚未充分覆盖。真值仍需要专家标注或构造协议，动态重放也会带来成本和环境漂移问题。

## 6. Use for my thesis

这是当前课题最强的归因基准对照。我的工作不能只声称“把日志变成 trace”，而应说明系统级 eBPF 信号能否在完整应用 trace 之外增加责任边证据。Adapter 应保留输入、输出、工具、环境和架构元数据，并输出 provenance；反事实接口可以借鉴其动态重放思想，但要明确无法重放时只能报告 observational localization。

## 7. Claim–evidence rows

| Claim | Evidence | Status |
|---|---|---|
| 完整执行轨迹有助于细粒度归因 | 摘要；§4 的观测消融 | `VERIFIED` |
| 决定性步骤不等于时间上最早的错误 | §2 Problem Definition | `VERIFIED` |
| 可执行环境能支持动态反事实验证 | §3 trace collection、§4 dynamic configuration | `VERIFIED` |
| eBPF 系统事件能增加 Agent/Edge 归因信息 | 本论文未研究 | `UNVERIFIED` |
