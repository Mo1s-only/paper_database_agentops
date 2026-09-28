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
