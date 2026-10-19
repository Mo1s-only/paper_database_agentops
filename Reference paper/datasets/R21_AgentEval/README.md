# R21 — AgentEval：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文与官方仓库）。`

本地论文：[05_reliability_evaluation/Assessing_and_Verifying_Task_Utility_in_LLM-Powered_Applications_EMNLP2024.pdf](<../../05_reliability_evaluation/Assessing_and_Verifying_Task_Utility_in_LLM-Powered_Applications_EMNLP2024.pdf>)

## 分类

任务效用评价；数学与具身环境

## 论文实验使用的数据

MATH 共 12,500 题，论文选取 120 个 level-5 难题；另使用 ALFWorld household task。

## 获取与本地状态

官方仓库提供评测实现和部分运行产物；精确 120 题选择与 ALFWorld 环境依赖需要按代码配置重建，未重复下载完整上游资源。

## 本地数据

- 无。本次未下载的原因见“获取与本地状态”。

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [官方仓库](https://github.com/Narabzad/AgentEval)
- [MATH](https://github.com/hendrycks/math)
- [ALFWorld](https://github.com/alfworld/alfworld)

## 对当前论文的用途

可参考自动生成评价准则，但需单独验证 LLM judge 与人工评分的一致性。
