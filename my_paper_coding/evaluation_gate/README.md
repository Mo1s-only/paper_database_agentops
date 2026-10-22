# 跨任务归因与反事实验证门

这个目录验证三个研究缺口的最小闭环：

1. 三类故障的 Agent/Step/Edge 归因；
2. 同一归因规则在不同任务 schema 上的迁移；
3. 修复责任事件后任务是否成功、修改无关事件后任务是否仍失败。

运行：

```powershell
python .\cross_task_counterfactual.py --out-dir .\results\gate-20260928 --repetitions 3
```

当前任务是确定性本地 harness，不调用模型、不访问网络，也不替代真实 AgentSight 运行。它用于先固定评测协议，之后再把真实 AgentSight 事件接入同一接口。

## 标签隔离更正与新协议

旧 `cross_task_counterfactual.py` 将 `task_name/spec` 传入预测、任务判据和反事实逻辑，旧 9/9 仅是标签条件的 harness 试跑，不是盲测归因或独立反事实效果。更正记录见 `gate-report.md`。

零 API 的隔离版本位于 `blind_counterfactual.py` 与 `prepare_blind_counterfactual_fixtures.py`；它使用 trace-only predictor（见 `failure_pilot/blind_attribution_eval.py`），冻结候选后按独立 repair plan 做修复/无关控制，再独立评分。测试见 `test_blind_counterfactual.py`；9 条 fixture 的协议检查及边界见 `lab/experiment/blind_counterfactual_protocol_20261022/protocol-report.md`。合成 9/9 不代表论文结果。
