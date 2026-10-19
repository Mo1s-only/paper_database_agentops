# R13 — Beyond Natural Language：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文、官方仓库和本地文件）。`

本地论文：[03_diagnosis_localization/Beyond Natural Language.pdf](<../../03_diagnosis_localization/Beyond Natural Language.pdf>)

## 分类

推理与多智能体通信格式

## 论文实验使用的数据

单体推理使用 Logic Grid、Coin Flip、Information Essentiality、Minute Mysteries QA、AQuA；多智能体通信使用 HotpotQA、WikiHop、NarrativeQA。

## 获取与本地状态

官方 AutoForm 仓库提供论文所用 data 目录。已下载 16 个文件、约 21 MB，固定提交 8df9450。

## 本地数据

- [`shared_data/AutoForm_exact_subsets`](../shared_data/AutoForm_exact_subsets)

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [官方仓库](https://github.com/thunlp/AutoForm)

## 对当前论文的用途

可用于分析消息格式、token 成本和通信效率；不应把格式效率结果直接解释为故障归因准确率。
