# R27 — DREAM：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文与官方数据页）；AUTHOR_INPUT_NEEDED（接受数据条款后方可下载）。`

本地论文：[06_agent_evaluation_metrics/DREAM_ACL2026.pdf](<../../06_agent_evaluation_metrics/DREAM_ACL2026.pdf>)

## 分类

深度研究报告；自适应评价

## 论文实验使用的数据

主要使用 DeepResearch Bench：6 个 agent、50 个查询、300 份报告；另构造 20 个时效查询×3 个截止时间、10 个复杂查询的 20 份配对报告，以及 15 组对抗事实声明。

## 获取与本地状态

论文关联的 LiveResearchBench 当前需要接受 Hugging Face 访问条款。文件页面显示规模较小，但访问受限，因此只保留链接，不绕过授权。

## 本地数据

- 无。本次未下载的原因见“获取与本地状态”。

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [LiveResearchBench](https://huggingface.co/datasets/Salesforce/LiveResearchBench)

## 对当前论文的用途

适合借鉴时效性、事实性和覆盖率评价；与运行时故障归因的标签语义不同。
