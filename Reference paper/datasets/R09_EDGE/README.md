# R09 — EDGE: Error Dependency Graph：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文和官方数据源）。`

本地论文：[02_failure_attribution/EDGE_Error_Dependency_Graph.pdf](<../../02_failure_attribution/EDGE_Error_Dependency_Graph.pdf>)

## 分类

多错误轨迹；错误依赖边与反事实重放

## 论文实验使用的数据

TRAIL 的 148 条轨迹（官方说明含 841 个错误）以及 MAST/MAD 中 393 条 AutoGen 轨迹。

## 获取与本地状态

TRAIL 已下载为 30 MB 压缩包。MAST 完整文件约 200 MB，只保留官方链接；393 条子集需按论文筛选条件从完整集重建。

## 本地数据

- [`shared_data/TRAIL_benchmarking_148_traces.zip`](../shared_data/TRAIL_benchmarking_148_traces.zip)

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [EDGE 官方仓库](https://github.com/JuneHou/EDGE)
- [TRAIL](https://github.com/patronus-ai/trail-benchmark)
- [MAST 数据](https://huggingface.co/datasets/mcemri/MAST-Data/tree/main)

## 对当前论文的用途

是当前论文未来做边级传播归因最相关的数据；下一步需把 TRAIL span 标注映射到本项目事件和关系 schema。
