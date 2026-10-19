# R22 — AgentBench：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文、官方仓库和本地文件）。`

本地论文：[06_agent_evaluation_metrics/AgentBench_ICLR2024.pdf](<../../06_agent_evaluation_metrics/AgentBench_ICLR2024.pdf>)

## 分类

通用交互式 Agent 环境

## 论文实验使用的数据

8 个环境：Operating System、Database、Knowledge Graph、Digital Card Game、Lateral Thinking Puzzle、House Holding（ALFWorld）、Web Shopping（WebShop）、Web Browsing（Mind2Web）。论文开发/测试集合计 269/1,014 个任务。

## 获取与本地状态

官方仓库 data 目录已下载：125 个文件、约 30.6 MB，固定提交 d1e4a10。部分环境仍需数据库、容器或外部资源，本地 data 不是一键可运行的完整环境镜像。

## 本地数据

- [`shared_data/AgentBench_data`](../shared_data/AgentBench_data)

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [官方仓库](https://github.com/THUDM/AgentBench)

## 对当前论文的用途

可提供多类型 agent 任务，但若用于归因前观测实验，应先选一个环境冻结依赖并记录每轮动作/观察。
