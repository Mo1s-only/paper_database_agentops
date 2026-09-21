# AgentOps 文献库

本库按 Agent 链路整理：

```text
观测 → 故障归因 → 诊断定位 → 预测/早期预警 → 可靠性与评测
```

分类依据是论文主要解决的问题，而不是论文是否只属于一个环节。跨环节论文只放在一个主分类中，并在索引里注明关联环节。`已下载/待精读` 表示已保存论文文件但尚未完成本地精读笔记；它不代表论文结论已经被本课题验证。

## 分类目录

- `01_agent_observation/`：运行时观测、日志/trace、信息采集和可观测性基础设施。
- `02_failure_attribution/`：识别责任 Agent、责任步骤、依赖传播和故障归因基准。
- `03_diagnosis_localization/`：错误检测、根因定位、调试、工具错误诊断和修复线索。
- `04_prediction_early_warning/`：失败风险、掉队/退出、异常趋势和故障诱导下的提前预警。
- `05_reliability_evaluation/`：可靠性、任务效用、系统评测和稳定性分析。
- `06_new_candidates/`：预留给下一轮检索的候选论文；已纳入本轮的论文已移动到主分类。

## 新增论文

本轮从 ACL Anthology 官方页面检索并下载三篇近年论文：

| 论文 | Venue/年份 | 主分类 | 状态 |
|---|---|---|---|
| Tools Fail: Detecting Silent Errors in Faulty Tools | EMNLP 2024 | 诊断定位 | 已下载/待精读 |
| Assessing and Verifying Task Utility in LLM-Powered Applications | EMNLP 2024 | 可靠性与评测 | 已下载/待精读 |
| Breaking Agents: Compromising Autonomous LLM Agents Through Malfunction Amplification | EMNLP 2025 | 预测/早期预警 | 已下载/待精读 |

## 检索记录

- 检索日期：2026-09-21
- 主要来源：ACL Anthology、OpenReview；优先保留 ACL/EMNLP 等正式会议论文和官方 PDF。
- 检索词：`multi-agent LLM failure attribution`、`agent diagnosis`、`agent observability tracing`、`agent failure prediction`、`silent tool errors`。
- 纳入标准：近几年、正式会议/期刊或与 AgentOps 链路直接相关、存在可核验的官方论文页面。
- 排除标准：只有博客/产品文档、无法核验正式发表信息、与 Agent 观测/归因/诊断/预测/评测关系弱的材料。
