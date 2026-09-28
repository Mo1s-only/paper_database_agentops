# AgentSight attach-mode 真实观测探针

**版本**：v0.1
**时间**：2026-09-28
**目的**：修复 WSL2 launch 模式导致的 0 事件问题，并把一个真实 Claude 进程的工具调用与独立故障真值放到同一次运行中。

## 运行方式

在 WSL2 root shell 中运行：

```bash
cd /mnt/c/Users/mobao/Desktop/论文方向/my_paper_coding/failure_pilot
./capture_agentsight_attach.sh
```

脚本使用 AgentSight 已验证的 attach 流程：先启动 `agentsight record -c claude`，再启动 Claude；同时启动 `agentsight debug process` 保存原始流。凭据仍从外部 `agentsight/test/.env` 读取，不写入仓库。

## 受控故障

Claude 只能调用一次 Bash，执行本地 `fake_inventory.py alpha`。假工具返回格式合法的 `status=ok, available=0`，而任务要求为 `available=1`。`probe-truth.json` 单独保存预期值、观察值和责任步骤，不将 `fault_injected` 标签放进 Claude 的输入。

## 通过条件

- Agent 进程退出码为 0；
- `record.log` 报告的 API calls、tokens、execs 或 files 至少有一类非零；
- `db-rows.txt` 和 `report-*.txt` 能追溯到本次数据库；
- `probe-truth.json` 与 `claude-run.log` 可以离线比对。

这不是论文结果。它只验证 AgentSight 真实观测链能否与受控故障真值共存；后续仍需增加多 Agent 运行和独立人工/反事实标签。
