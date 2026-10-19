# R18 — AgentDropout：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文与官方仓库）；本地包只覆盖其中部分基准。`

本地论文：[04_prediction_early_warning/AgentDropout.pdf](<../../04_prediction_early_warning/AgentDropout.pdf>)

## 分类

推理/数学/代码；拓扑剪枝和成本

## 论文实验使用的数据

MMLU、GSM8K、AQuA、MultiArith、SVAMP、HumanEval，与信息传播类研究有较强重叠。

## 获取与本地状态

官方仓库主要提供数据加载脚本，没有统一内置全部数据。为避免重复，已下载的 EIB 小型数据只在 shared_data 保存一份。

## 本地数据

- [`shared_data/EIB_selected_datasets`](../shared_data/EIB_selected_datasets)

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [官方仓库](https://github.com/wangzx1219/AgentDropout)

## 对当前论文的用途

可用于拓扑干预与 token/性能权衡；复现要记录每次删除的 Agent 和通信边。
