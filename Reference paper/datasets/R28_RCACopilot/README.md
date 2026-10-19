# R28 — RCACopilot：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文）；数据访问状态为非公开。`

本地论文：[03_diagnosis_localization/RCACopilot_Automatic_Root_Cause_Analysis_EuroSys2024.pdf](<../../03_diagnosis_localization/RCACopilot_Automatic_Root_Cause_Analysis_EuroSys2024.pdf>)

## 分类

工业事故；多源证据与根因类别

## 论文实验使用的数据

Microsoft Transport 一年内 653 个 incidents，按 75%/25% 划分训练/测试，由专家标注根因类别，并结合告警、日志和处理记录。

## 获取与本地状态

数据包含企业内部事故信息，论文未提供公开下载。这里只记录规模和数据类型，不创建替代或合成文件。

## 本地数据

- 无。本次未下载的原因见“获取与本地状态”。

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- 无已核验的独立公开数据链接；以本地论文为证据。

## 对当前论文的用途

可借鉴 incident handler 的证据收集流程和弱分类任务定义，不能作为可复现公开基准。
