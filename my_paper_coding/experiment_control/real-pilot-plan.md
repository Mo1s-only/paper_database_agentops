# 下一轮真实 AgentSight Pilot 计划

**版本**：v0.1
**时间**：2026-09-28
**状态**：`FIRST_CASE_COMPLETED_BUDGET_STOP`

这份清单只冻结实验设计，不会启动 Claude 或其他网络请求。三类真实 pilot 各设计两个 Agent 调用，共 6 次 API 调用；按当前观测到的单次最高成本 0.13 USD 估算，上限约 0.78 USD，硬停止线为 1.00 USD。

| case | 任务 | 故障 | 责任标签 | 预计调用 |
|---|---|---|---|---:|
| `inventory-silent-tool` | 库存检查 | 静默工具错误 | Agent B / Bash 工具步骤 | 2 |
| `service-error-propagation` | 服务重启 | 错误传播 | Agent B / Bash 工具步骤 | 2 |
| `retrieval-routing-error` | 文档检索 | 路由/角色错误 | Orchestrator / route 步骤 | 2 |

每个 case 先只运行 1 次。只有同时满足 AgentSight 数据非零、任务真值独立、归因输出可复核、反事实结果可复验，才考虑重复运行。

## 执行顺序

1. 运行 `prepare_real_pilot.py` 生成清单；
2. 用 `budget_guard.py` 检查累计成本和本批次上限；
3. 只执行一个 case；
4. 读取 `cost.json` 和 `analysis.json`；
5. 若质量门失败，停止，不执行剩余 case。

## 已执行结果

`inventory-silent-tool` 已在 `results/real-pilot-inventory-20260928-r2/` 完成。两次 API 调用实际成本为 `0.218846 USD`，AgentSight 数据非零，归因与受控真值匹配，离线反事实门通过。当前全局账本累计 `0.944059 USD`，达到原定 `1.00 USD` 停止线附近，因此剩余两个 case 暂停，不能在没有新预算授权的情况下继续调用。

## 当前不做的事情

- 不直接执行 6 次调用；
- 不把合成 pilot 的 1.0 当作真实结果；
- 不在没有独立真值的情况下扩展到 30–50 条；
- 不修改 `lab/agentsight`。
