# 第 11 章：项目复现与数据工程

本章正文：[详细教程](详细教程.md)；学习后完成：[练习与验收](练习与验收.md)；最后对照：[练习与验收答案](练习与验收答案.md)。

## 本章定位

这一章把前十章连接到本项目真实资产。重点不是再次跑出“13/13”，而是理解证据如何生成、校验、归档、配对并进入后续归因实验。

## 学习目标

- 复现 AgentSight 的预检、运行、验证和归档流程。
- 理解 `session.db` 七类核心表和原始日志之间的关系。
- 理解 Watson 的离线流程、真实 demo 与证据边界。
- 掌握 experiment_id、版本、配置、原始数据、派生数据和报告的组织。
- 处理请求—响应配对、缺失事件、重复记录和数据脱敏。

## 建议顺序

### 1. 只读理解

先读快速复现指南、输出数据说明和历史实验报告，不调用模型。

### 2. 无成本预检

确认 WSL2、Linux 内核、tracefs、权限、AgentSight 与 Claude 可执行状态。

### 3. 运行与验证

真实运行前记录环境、版本、模型、任务、工具权限和预算。`13/13` 只证明观测链路通过，不证明故障归因有效。

### 4. 数据审计

以 `session.db`、`db-rows.txt` 和 `record.log` 为主要来源；原始事件流用于追溯，摘要视图不能相加当真值。

### 5. 配对与统一 schema

优先解决 request–response 配对，目标 Precision 不低于 0.95；不确定配对应标记或舍弃，不能只按最近时间戳强连。

## 项目内材料

- [AgentSight 快速复现](../../lab/agentsight/快速复现AgentSight.md)
- [AgentSight 输出数据说明](../../lab/agentsight/results/AgentSight输出数据说明.md)
- [AgentSight 结果组织规则](../../lab/agentsight/results/README.md)
- [Watson 论文复现说明](../../lab/Watson/docs/thesis/README.md)
- [P0 请求—响应配对](../../my_paper_coding/p0_pairing/README.md)
- [当前研究进展](../../my_paper/进展/进展_v0.1_2026-09-21.md)

## 本章完成标准

从一个真实实验目录生成可复核的一页报告：任务、版本、成功判据、关键事件、配对质量、缺失证据、隐私处理和可支持/不可支持的结论。
