# R04 — Understanding the Information Propagation Effects in Multi-Agent Systems：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文和官方仓库）。`

本地论文：[01_agent_observation/Understanding the Information.pdf](<../../01_agent_observation/Understanding the Information.pdf>)

## 分类

推理/数学/代码；通信拓扑与错误传播

## 论文实验使用的数据

MMLU、GSM8K、AQuA、MultiArith、SVAMP、HumanEval 六个公开基准。

## 获取与本地状态

官方实现现位于 EIB_learner。仓库 datasets 目录只内置/提供部分数据与下载脚本，并不等同于六个基准的完整统一镜像。已保存其中可直接取得的 6 个文件。

## 本地数据

- [`shared_data/EIB_selected_datasets`](../shared_data/EIB_selected_datasets)

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [官方仓库](https://github.com/se7esx/EIB_learner)

## 对当前论文的用途

可作为通信边、拓扑和错误信息传播实验的语义任务输入；复现时需补齐未内置的上游数据。
