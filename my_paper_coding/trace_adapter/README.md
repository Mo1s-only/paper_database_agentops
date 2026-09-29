# Trace Adapter 输入索引（v0.2）

这个目录把现有实验结果整理成 Adapter 可读取的证据清单。它不改动 `lab/`，也不移动或复制原始日志；`structured_runs/` 中保存的是每次运行的 `run.json` 清单、相对路径、文件格式、大小和 SHA256。Adapter 先读取清单，再按 `category` 访问原始目录，因而不会依赖某一个固定文件名或固定实验。

## 统一运行目录的逻辑分层

每次运行都被映射为以下几类输入：

| category | 含义 | 典型文件 | Adapter 用途 |
| --- | --- | --- | --- |
| `raw_observation` | AgentSight/eBPF 或 HTTP 观测的原始证据 | `session.db`、`raw-stream.log`、`record.log`、`report-*.txt`、`ssl-http.jsonl` | 生成系统事件，保留原始时间、进程、线程、网络和文件证据 |
| `app_log` | Agent 框架或应用层日志 | `claude-agent-*.log`、`claude.json`、`claude.err`、agent exit 文件 | 提取 Agent、步骤、工具调用、请求/响应和会话标识 |
| `task_context` | 任务输入、路由和输出工件 | `workspace/route.json`、`workspace/decision.json`、`marker.txt` | 建立任务、Agent 角色和输出对象 |
| `validator` | 独立任务判据或责任真值 | `ground_truth*.json`、`truth*.json`、`oracle*.json` | 只用于离线评估，不能作为观测事件或推理输入 |
| `derived` | 已有分析或派生轨迹 | `trace.jsonl`、`analysis.json`、`counterfactual.json`、`pairing-analysis.json` | 对比 Adapter 输出；不能替代原始证据 |
| `metadata` | 运行和退出信息 | `run-info.txt`、`*-exit.txt` | 解释运行状态和失败原因 |

清单中的 `signals` 只提取模型名、会话 ID、用量和费用等元数据，不复制 prompt 或 response。原始 `app_log` 可能包含敏感文本，发布前要单独脱敏。

## 生成索引

在仓库根目录执行：

```powershell
python .\my_paper_coding\trace_adapter\build_run_index.py
```

输出位置为 `my_paper_coding/trace_adapter/structured_runs/`：

```text
structured_runs/
├── run-index.json                 # 全部运行的机器可读目录
├── run-index.jsonl                # 逐行消费版本
├── failure_pilot/<run-id>/run.json
├── p0_pairing/<run-id>/run.json
└── evaluation_gate/<run-id>/run.json
```

脚本是只读发现器：它只读取现有结果并写入新的索引文件。重复运行会更新 `indexed_at` 和文件哈希，不会修改原始实验结果。

## 生成带来源定位的证据记录

在生成索引后执行：

```powershell
python .\my_paper_coding\trace_adapter\normalize_runs.py
```

它会在 `structured_runs/normalized/<family>/<run-id>/evidence-events.jsonl` 中写出证据级记录。每条记录都带有 `source.path` 和 `source.line`，并区分：

- `observed`：从 Claude 结果日志或 HTTP 原始观测中直接解析出的字段；
- `derived_untrusted`：从已有 `trace.jsonl` 读取的派生事件，只用于对照，不能作为 ground truth。

对于当前的最终结果日志，记录会明确标记 `final_result_record_only`、`no_step_or_tool_events_in_source` 和 `timestamp_unavailable_in_source`。这表示脚本已经把可用信息结构化，但不会把最终摘要伪装成完整 Agent 执行链。HTTP 记录保留 PID/TID、请求方法、路径、状态码和原始行号；当原始数据没有 session 或 Agent 字段时，记录会保留 `null` 并标注限制。

`run-metadata.template.json` 是下一次实验启动前应填写的元数据模板，重点补齐 Git commit、软件版本、命令、采集模式、时钟不确定度、session/request/marker 和 PID 列表。历史运行缺失的这些字段不能事后可靠重建。

对真实 AgentSight 运行，还可以执行单次链路检查：

```powershell
python .\my_paper_coding\trace_adapter\smoke_check.py `
  .\my_paper_coding\failure_pilot\results\<run-id> `
  --normalized .\my_paper_coding\trace_adapter\structured_runs\normalized\failure_pilot\<run-id>\evidence-events.jsonl
```

该检查会读取 SQLite 中的 `llm_calls`、`tool_calls`、`audit_events`、`process_nodes` 等表，统计真实 API 调用、AgentSight 观测和任务工件是否存在。它不会生成责任标签；只有 `unified_trace_ready` 为 `true` 后，才进入跨层对齐和归因阶段。

## Adapter 的最小输入契约

Adapter 应当对每个 `run.json`：

1. 根据 `artifacts[].category` 读取原始观测和应用日志；
2. 使用应用日志中的会话、Agent、工具和步骤标识，与系统层 PID/TID、时间和网络事件对齐；
3. 把 `task_context` 作为任务对象和输出对象来源；
4. 把 `validator` 作为独立 oracle，只在离线评分阶段使用；
5. 生成新的规范化 `trace.jsonl` 和 provenance/responsibility graph，并保留每条边引用的原始 artifact 路径与事件定位；
6. 对 `warnings` 中的缺失项输出 `unknown` 或 `abstain`，不能用 `derived` 文件反推缺失的原始事实。

规范化脚本已经为现有结果完成了第一轮证据索引，但它不会补造历史上不存在的应用事件、时间戳或关联 ID。要真正消除这些缺口，下一次真实运行必须在同一个 run 目录中同时保存完整应用 JSONL、AgentSight 原始文件、任务 oracle 和运行元数据。

## 完整性和证据边界

`completeness` 记录本次运行是否具备原始观测、应用日志、任务上下文、独立判据和派生结果。`warnings` 是 Adapter 的前置检查结果。`derived_outputs_are_not_ground_truth` 固定为 `true`，避免把之前的人工或 manifest 驱动分析误当成自动归因证据。

当前目录描述的是已有数据的结构化入口，不代表已经完成通用 Trace Adapter。下一步需要实现事件解析、跨层对齐、冲突处理和缺失证据下的 abstention，并在不同任务、故障和 Agent 框架上验证。
