# R06 — Seeing the Whole Elephant / TraceElephant：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文与官方数据页）。`

本地论文：[02_failure_attribution/TraceElephant_Seeing_the_Whole_Elephant.pdf](<../../02_failure_attribution/TraceElephant_Seeing_the_Whole_Elephant.pdf>)

## 分类

全轨迹失败归因；可复现实验环境

## 论文实验使用的数据

共 380 次执行、220 条失败轨迹：Captain-Agent/GAIA 126/73、Captain-Agent/AssistantBench 21/12、Magentic-One/GAIA 119/74、Magentic-One/AssistantBench 30/17、SWE-Agent/SWE-Bench 84/44（执行数/失败数）。

## 获取与本地状态

官方 Hugging Face 数据包约 597 MB，超过本项目 100 MiB 本地阈值，因此只保留链接。许可证为 CC BY 4.0。

## 本地数据

- 无。本次未下载的原因见“获取与本地状态”。

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [官方仓库](https://github.com/TraceElephant/TraceElephant)
- [数据集](https://huggingface.co/datasets/TraceElephant/TraceElephant/tree/main)

## 对当前论文的用途

适合后续检验“完整观测是否提高归因”，但下载前需准备约 0.6 GB 空间并固定数据版本。
