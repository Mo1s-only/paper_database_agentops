# API 成本控制策略

**版本**：v0.1
**时间**：2026-09-28

1. 先用确定性本地 harness 验证 schema、归因器和反事实协议；这类运行不调用 API。
2. 真实 AgentSight 运行先做单故障、单任务的最小 pilot，不直接执行 30–50 条。
3. 每次真实运行必须保存 Claude JSON 日志，并用 `cost_ledger.py` 记录实际成本。
4. 预算预检不通过时停止，不启动 Claude；脚本 `budget_guard.py` 不发起网络请求。
5. 只有当一条真实 pilot 同时满足：AgentSight 有非零事件、真值可独立生成、反事实可复验，才考虑扩大样本。
6. 不把缓存 token、模型 warning 或 AgentSight 观测数量误写成新的方法效果。

已有真实日志显示：单 Agent 探针约 0.095757 USD，两 Agent 探针约 0.218011 USD。后续预算应按单次最高观测成本加安全余量估算。
