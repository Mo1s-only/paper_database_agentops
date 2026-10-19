# R14 — Tools Fail：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文中的规模）；UNVERIFIED（论文精确派生实例未在当前仓库发布）。`

本地论文：[03_diagnosis_localization/Tools_Fail_Detecting_Silent_Errors_in_Faulty_Tools_EMNLP2024.pdf](<../../03_diagnosis_localization/Tools_Fail_Detecting_Silent_Errors_in_Faulty_Tools_EMNLP2024.pdf>)

## 分类

工具静默错误；动作规划与目标检测

## 论文实验使用的数据

论文构造计算器工具错误任务，并从 ALFRED 派生 action planner 490 条、object detector 214 条实验实例。

## 获取与本地状态

论文指向的 tools-fail 官方仓库当前仅有说明文件，未发现可下载的数据文件，因此只保留仓库链接。

## 本地数据

- 无。本次未下载的原因见“获取与本地状态”。

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [官方仓库](https://github.com/jiminsun/tools-fail)
- [ALFRED](https://github.com/askforalfred/alfred)

## 对当前论文的用途

可作为工具返回值正确但语义错误的故障模型来源；本地实验应自行保存注入规则与实例 ID。
