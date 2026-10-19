# R11 — Watson：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文实验章节）；精确 MMLU 子集 ID 未在本地材料中确认。`

本地论文：[03_diagnosis_localization/Watson.pdf](<../../03_diagnosis_localization/Watson.pdf>)

## 分类

推理与软件修复；隐式认知轨迹诊断

## 论文实验使用的数据

MMLU 全集 14,042 题，论文从中构造三个各 374 题的子集；软件工程实验使用 SWE-bench Lite 300 个 issue，并运行 AutoCodeRover 和 OpenHands。

## 获取与本地状态

基准公开但模型运行轨迹体量和依赖较大，未重复镜像。精确 374 题子集需要论文代码或采样配置才能保证一致。

## 本地数据

- 无。本次未下载的原因见“获取与本地状态”。

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [MMLU](https://github.com/hendrycks/test)
- [SWE-bench](https://github.com/SWE-bench/SWE-bench)

## 对当前论文的用途

可借鉴“恢复推理轨迹后再检查”的诊断思路，数据准备必须同时固定 agent 实现和仓库镜像。
