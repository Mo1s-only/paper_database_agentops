# TraceElephant → 本地统一 schema 映射

**版本**：v0.1
**时间**：2026-09-28
**来源核对**：TraceElephant 公开仓库 `0ce8abb2855de9f454f27f6b0795a4b7e6c8d5fc`

我在临时目录读取了公开仓库的 evaluator 和 README，确认其新格式为：

- `trace_metadata.json`：`task_instruction`、`ground_truth`、`tests_status`、`mistake_agent`、`mistake_step`、`agent_system_intro`；
- `step_records.json`：逐步的 `agent_name`、`input`、`output`。

`adapt_traceelephant.py` 将这些字段转换为本地 `agentops-trace-v0.1` 和 `agentops-ground-truth-v0.1`。映射关系如下：

| TraceElephant 字段 | 本地字段 | 说明 |
|---|---|---|
| 任务目录名 | `run_id` | 没有强行伪造上游运行 ID |
| `step_records[].agent_name` | `agent_id` | 保留原始 Agent 名称 |
| 步骤序号或 `step_id` | `step_id` | 若原数据没有显式 ID，则使用顺序号 |
| `step_records[].input` | `input_summary` | 原始输入对象 |
| `step_records[].output` | `output_summary` | 原始输出或字符串 |
| `mistake_agent` | `responsible_agent` | 外部标注真值 |
| `mistake_step` | `responsible_step` | 外部标注真值 |
| `tests_status` | `task.finish.status` | 仅做成功/失败粗粒度映射 |

当前不能从这两个文件直接构造 AgentSight 的进程、网络、文件或模型调用事件，也不能凭空补出责任 Edge。因此适配后的 `responsible_edge` 和 `evidence_event_ids` 保留为空，等待原始 trace 中的更细粒度字段或本地重放补充。

## 运行示例

```powershell
python .\adapt_traceelephant.py `
  --task-dir C:\path\to\trace-task `
  --out-dir .\results\traceelephant-task-01
```

原始数据应放在仓库外的临时目录；适配后的 prompt、response 和路径信息也应先脱敏，确认许可后再纳入实验集。
