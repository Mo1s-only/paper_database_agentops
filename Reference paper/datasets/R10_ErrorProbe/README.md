# R10 — Towards Self-Improving Error Diagnosis / ErrorProbe：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文对数据集的描述）；UNVERIFIED（TracerTraj 独立公开下载地址）。`

本地论文：[02_failure_attribution/ErrorProbe_Self_Improving_Error_Diagnosis_ACL2026.pdf](<../../02_failure_attribution/ErrorProbe_Self_Improving_Error_Diagnosis_ACL2026.pdf>)

## 分类

代码代理轨迹；错误诊断和验证记忆

## 论文实验使用的数据

实验使用 TracerTraj 的代码生成子集，以及 Who&When-Algorithm-Generated 和 Who&When-Hand-Crafted 两个子集。论文将 TracerTraj 描述为来自 AgenTracer 的约 2.5K 轨迹资源。

## 获取与本地状态

Who&When 已本地保存。当前未定位到可核验的 TracerTraj 官方独立下载页，因此仅记录论文中的使用事实，不提供猜测链接。

## 本地数据

- [`shared_data/WhoAndWhen_184`](../shared_data/WhoAndWhen_184)

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [Who&When](https://github.com/ag2ai/Agents_Failure_Attribution)

## 对当前论文的用途

可用于设计反向错误候选检索与执行验证；在 TracerTraj 来源确认前，不应声称完成该基准复现。
