# R30 — OpenRCA 2.0：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文数据构造描述）；UNVERIFIED（公开数据 artifact 尚未找到）。`

本地论文：[03_diagnosis_localization/OpenRCA_2.0_Causal_Process_Supervision_2026.pdf](<../../03_diagnosis_localization/OpenRCA_2.0_Causal_Process_Supervision_2026.pdf>)

## 分类

因果过程监督；节点/边/路径真值

## 论文实验使用的数据

从 8,137 次故障注入运行中精选 500 个实例，覆盖 TrainTicket、OpenTelemetry Demo、DeathStarBench Hotel Reservation 三个系统和 27 类 chaos primary kind；每例包含 traces、metrics、logs 与因果图。

## 获取与本地状态

论文说明匿名预览/完整包随投稿提供，并计划接受后公开 PAVE artifact；截至本次整理未找到可核验的公开数据仓库。仅记录论文链接和三个上游系统。

## 本地数据

- 无。本次未下载的原因见“获取与本地状态”。

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [论文](https://arxiv.org/abs/2606.27154)
- [TrainTicket](https://github.com/FudanSELab/train-ticket)
- [OpenTelemetry Demo](https://github.com/open-telemetry/opentelemetry-demo)
- [DeathStarBench](https://github.com/delimitrou/DeathStarBench)

## 对当前论文的用途

其 root/node/edge/path/evidence-query 层次可直接作为后续归因数据协议的对齐目标。
