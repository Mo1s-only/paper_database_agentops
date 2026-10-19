# R19 — Breaking Agents：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文中的实验规模）；UNVERIFIED（独立数据发布位置）。`

本地论文：[04_prediction_early_warning/Breaking_Agents_Malfunction_Amplification_EMNLP2025.pdf](<../../04_prediction_early_warning/Breaking_Agents_Malfunction_Amplification_EMNLP2025.pdf>)

## 分类

Agent 故障放大与攻击；工具环境

## 论文实验使用的数据

Agent Emulator 构造 144 个测试用例，覆盖 36 个 toolkits、300 余个工具；另含 Gmail Agent、CSV Agent 及多智能体案例。

## 获取与本地状态

这是运行时生成的攻击/交互用例集合。当前本地证据未确认独立公开静态数据包，因此保留论文定义，不伪造下载地址。

## 本地数据

- 无。本次未下载的原因见“获取与本地状态”。

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- 无已核验的独立公开数据链接；以本地论文为证据。

## 对当前论文的用途

可为循环调用、任务偏离和故障放大设计压力测试，并把攻击提示、工具调用和终止条件写入轨迹。
