# R26 — MultiAgentBench：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文、官方仓库和本地配置）。`

本地论文：[06_agent_evaluation_metrics/MultiAgentBench_ACL2025.pdf](<../../06_agent_evaluation_metrics/MultiAgentBench_ACL2025.pdf>)

## 分类

多智能体协作/竞争；里程碑 KPI

## 论文实验使用的数据

覆盖 ResearchTown、Bargaining、Werewolf、数据库错误分析、Coding、Minecraft 等场景。论文为任务构造测试用例；ResearchTown 使用 100 篇 ML/AI 论文，按 33/34/33 个易/中/难任务组织。

## 获取与本地状态

官方 MARBLE 仓库提供大量任务配置。已抽取 coding、database、werewolf、minecraft 等可直接核验的配置与小型映射文件，共 1,219 个文件、约 7.75 MB；它们是配置快照，不包含所有运行依赖和 ResearchTown 论文全文。

## 本地数据

- [`shared_data/MultiAgentBench_task_configs`](../shared_data/MultiAgentBench_task_configs)

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [官方仓库](https://github.com/ulab-uiuc/MARBLE)

## 对当前论文的用途

动态里程碑 KPI 和多种拓扑适合验证当前 trace schema 是否能跨协作模式工作。
