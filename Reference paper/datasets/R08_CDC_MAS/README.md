# R08 — CDC-MAS：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文实验设置与官方数据源）。`

本地论文：[02_failure_attribution/CDC-MAS_Automatic_Failure_Attribution.pdf](<../../02_failure_attribution/CDC-MAS_Automatic_Failure_Attribution.pdf>)

## 分类

因果归因；性能反转、Shapley值和因果发现

## 论文实验使用的数据

论文在 Who&When 与 TRAIL 两类互补数据上评估：前者提供 Agent/步骤失败归因，后者提供 span 级多错误标注。

## 获取与本地状态

两个数据源均为公开数据。已保存 Who&When 数据目录和 TRAIL benchmarking 压缩包；TRAIL 本地包约 30 MB。

## 本地数据

- [`shared_data/WhoAndWhen_184`](../shared_data/WhoAndWhen_184)
- [`shared_data/TRAIL_benchmarking_148_traces.zip`](../shared_data/TRAIL_benchmarking_148_traces.zip)

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [Who&When](https://github.com/ag2ai/Agents_Failure_Attribution)
- [TRAIL](https://github.com/patronus-ai/trail-benchmark)

## 对当前论文的用途

适合比较单根因与多错误场景的数据 schema，并为后续 Agent/step/edge 三层归因准备标签映射。
