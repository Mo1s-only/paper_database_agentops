# R05 — Which Agent Causes Task Failures and When?：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文、官方仓库和本地文件）。`

本地论文：[02_failure_attribution/Which Agent Causes Task Failures and When.pdf](<../../02_failure_attribution/Which Agent Causes Task Failures and When.pdf>)

## 分类

多智能体失败轨迹；Agent级与步骤级归因

## 论文实验使用的数据

Who&When 共 184 条失败轨迹，来自 127 个 agentic systems。Algorithm-Generated 部分基于 CaptainAgent 与 GAIA/AssistantBench；Hand-Crafted 部分基于 Magentic-One 与 AssistantBench，并加入 30 个 GAIA 任务。

## 获取与本地状态

官方仓库同时给出数据目录与 Hugging Face 页面。已下载仓库中的 184 个数据文件，固定提交 f4d2b6d。

## 本地数据

- [`shared_data/WhoAndWhen_184`](../shared_data/WhoAndWhen_184)

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [官方仓库](https://github.com/ag2ai/Agents_Failure_Attribution)
- [Hugging Face](https://huggingface.co/datasets/Kevin355/Who_and_When)

## 对当前论文的用途

可直接作为归因前数据模式设计的参考：保存 agent、step、失败标签及证据位置，并区分自动生成与人工构造轨迹。
