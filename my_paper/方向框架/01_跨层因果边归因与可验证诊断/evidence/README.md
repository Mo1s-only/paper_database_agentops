# Evidence 台账

本目录只记录本方向的 claim–evidence 映射，不复制论文 PDF、原始 trace 或代码。

建议表格：

| Claim ID | 主张 | Evidence ID | 来源路径/链接 | 状态 | 可写入位置 | 缺口 |
|---|---|---|---|---|---|---|
| C01 | 完整证据提高边级归因 |  |  | UNVERIFIED | 摘要/结果 | 需要 B4 vs B1 对照 |
| C02 | 反事实验证减少伪归因 |  |  | UNVERIFIED | 方法/结果 | 需要可重放样本 |
| C03 | 一条真实受控两 Agent 轨迹可以完成观测、统一归一化、边级归因和反事实审计 | E14 | `my_paper_coding/failure_pilot/results/real-pilot-inventory-20260928-r2/`、`my_paper_coding/failure_pilot/real-pilot-inventory-report.md` | VERIFIED（单条受控运行） | 实验设置/案例分析 | 需要其他故障、任务和重复样本；不能推出总体准确率 |

规则：

- 每个摘要数字必须指向冻结的实验 ID 和统计输出。
- 文献主张回到 PDF/官方页面，不只引用二手笔记。
- 负结果、异常和排除样本同样登记。
- `INFERRED` 不能在论文中改写成实验事实。
