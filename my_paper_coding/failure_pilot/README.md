# 受控失败归因 Pilot

这个目录是方向 01 的下一道研究门：用一个无网络、无随机数的两 Agent 工作流，固定制造一次“静默工具错误”，同时保存统一轨迹和独立真值。它不修改 `lab/agentsight`，也不把合成 pilot 当作论文结果。

## 运行

```powershell
python .\run_failure_pilot.py --out-dir .\results\pilot-01
python .\analyze_failure_pilot.py --run-dir .\results\pilot-01
```

脚本只使用 Python 标准库。`trace.jsonl` 是观测轨迹，`ground_truth.json` 是由故障注入配置单独写出的责任真值，`analysis.json` 是根据轨迹推断后与真值比对的结果。

## 故障定义

- Agent A 负责规划和汇总；Agent B 负责查询工具并做判断。
- 任务要求 `alpha` 的可用数为 1。
- 伪工具返回格式合法、状态为 `success`，但返回 `available=0`。
- 最终结果因此失败。
- 真值为 `responsible_agent=agent_b`、`responsible_step=agent_b.tool_call`，责任边为工具结果进入 Agent B 决策的边。

轨迹中不写入 `fault_injected=true` 等标签，以避免把真值泄漏给归因器。真值文件只用于离线评分。

## 解释边界

该 pilot 只证明：在一个确定性故障和小型统一 schema 下，可以复现“观测 → 归因 → 定位”的闭环。它不能证明真实多 Agent 系统上的泛化能力、统计显著性或方法优越性。下一步需要把同一 schema 接到 AgentSight 的真实事件，并增加多种故障、多个架构和独立人工/规则标注。

## AgentSight 真实观测探针

`capture_agentsight_attach.sh` 使用 WSL2 下已验证的 attach 模式记录真实 Claude 进程和本地假工具。不要使用 `agentsight record -- python3 ...` 代替它；当前环境的 launch 模式会出现目标成功但数据库为 0 的归因丢失。运行说明与本次结果见 `agentsight-attach-probe.md` 和 `agentsight-attach-report.md`。

`run_fault_matrix.py` 进一步对三类确定性故障各重复 3 次，并输出 9 条独立 trace/真值/分析结果；汇总说明见 `fault-matrix-report.md`。
