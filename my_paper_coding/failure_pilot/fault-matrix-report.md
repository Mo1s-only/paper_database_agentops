# 三类故障矩阵 Pilot

**版本**：v0.1
**时间**：2026-09-28

`run_fault_matrix.py` 对三类确定性故障各重复 3 次：

1. `silent_tool_error`：工具返回格式合法但数值错误；
2. `error_propagation`：工具错误被 Agent B 继续传播到最终汇总；
3. `routing_role_error`：编排器把任务路由给不匹配的角色。

每次运行分别写出 `trace.jsonl`、`ground_truth.json` 和 `analysis.json`。当前版本的规则归因器在 9/9 次运行中 Agent、Step、Edge 全部精确匹配。

这个结果只验证故障本体、统一 schema 和离线评分器的接口稳定性。所有运行由同一个确定性 harness 生成，不能支持真实 AgentSight 泛化、统计显著性或方法优越性结论。

下一步是把同样三类故障接到真实两 Agent attach 工作流，并让责任标签由独立规则、人工标注或可执行反事实产生。
