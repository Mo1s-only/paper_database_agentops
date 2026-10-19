# R23 — AgentBoard：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（官方 README 和论文）；UNVERIFIED（本次未取得压缩包大小）。`

本地论文：[06_agent_evaluation_metrics/AgentBoard_NeurIPS2024.pdf](<../../06_agent_evaluation_metrics/AgentBoard_NeurIPS2024.pdf>)

## 分类

过程级 Agent 评测；九类环境任务

## 论文实验使用的数据

9 个任务分四类：Embodied AI（AlfWorld、ScienceWorld、BabyAI）、Game（Jericho、PDDL）、Web（WebShop、WebArena）、Tool（Tool-Query、Tool-Operation）。

## 获取与本地状态

官方数据以 data.tar.gz 发布，并包含多种环境附加资源；Tool 与 Web 任务还依赖 API 或网络。Hugging Face 从本机超时且完整包大小未可靠取得，因此只保留官方链接。

## 本地数据

- 无。本次未下载的原因见“获取与本地状态”。

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [官方仓库](https://github.com/hkust-nlp/AgentBoard)
- [官方数据](https://huggingface.co/datasets/hkust-nlp/agentboard)

## 对当前论文的用途

过程进展率比最终成功率更适合观测实验；复现时应区分静态 test.jsonl 与外部环境资源。
