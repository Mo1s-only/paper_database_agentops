# R16 — GALA：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文、官方仓库和本地文件）。`

本地论文：[03_diagnosis_localization/GALA_Graph_Augmented_LLM_RCA_Microservices_ASE2026.pdf](<../../03_diagnosis_localization/GALA_Graph_Augmented_LLM_RCA_Microservices_ASE2026.pdf>)

## 分类

微服务多模态遥测；图增强根因分析

## 论文实验使用的数据

OnlineBoutique 90 个注入故障场景（17 服务中的 5 个服务，6 类故障，各 3 次）；TrainTicket 90 个场景（69 个微服务）；另评估 AegisLab 100 个采样故障、25 类故障。

## 获取与本地状态

官方仓库 data/annotated_dataset.csv 已下载，本地 data 目录约 0.21 MB，固定提交 24d1329。该文件是公开标注切片，不等于论文全部原始遥测。

## 本地数据

- [`shared_data/GALA_annotation`](../shared_data/GALA_annotation)

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [官方仓库](https://github.com/EvanTian233/GALA-for-RCA)

## 对当前论文的用途

适合参考服务依赖图与 metrics/logs/traces 的融合方式；论文规模不能从这一小型 CSV 反推。
