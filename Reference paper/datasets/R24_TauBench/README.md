# R24 — τ-bench：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文、官方仓库和本地文件）。`

本地论文：[06_agent_evaluation_metrics/TauBench_ICLR2025.pdf](<../../06_agent_evaluation_metrics/TauBench_ICLR2025.pdf>)

## 分类

工具代理可靠性；对话用户模拟与数据库状态

## 论文实验使用的数据

Retail 和 Airline 两个领域，包含 policy、工具、任务、初始数据库以及用户模拟器。核心评价检查最终数据库状态和 pass^k。

## 获取与本地状态

官方仓库 tau_bench 包已下载：约 8.4 MB、100 个文件，固定提交 59a200c。运行仍需要模型/API 配置。

## 本地数据

- [`shared_data/TauBench_package`](../shared_data/TauBench_package)

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [官方仓库](https://github.com/sierra-research/tau-bench)

## 对当前论文的用途

很适合做重复运行可靠性和状态变更审计；应保存任务输入、工具调用、数据库 diff 与每次运行结果。
