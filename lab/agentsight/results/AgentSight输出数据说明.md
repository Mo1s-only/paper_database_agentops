# AgentSight 输出数据说明

本文档说明一次 AgentSight 端到端实验会产生哪些输出文件、每个文件如何解释，以及如何重复运行实验。实验脚本位于 `lab/agentsight/source/thesis_adapter/test/`，结果默认写入该脚本目录下的 `out/`；本仓库整理后的历史结果位于 `lab/agentsight/results/upstream/`。

## 一 实验产生的证据链

```text
Claude Code 执行任务
    ↓
进程与文件事件
    ↓
工具调用和模型请求
    ↓
Token、网络端点和资源采样
    ↓
SQLite session.db + 可读报告 + 原始事件流
```

一次成功实验至少应同时看到：Agent 的最终输出、工作区的 `hello.txt`、非空进程/审计表、非空 LLM/Token 表、工具调用和网络端点。

## 二 输出文件说明

### `claude-run.log`

Claude Code 自身的 JSON 输出。用于确认 Agent 是否返回结果、使用了什么模型、API 调用耗时、Token 和费用信息。它只能证明 Agent 返回了结果，不能单独证明文件真的写入；文件副作用要结合 workspace 和 AgentSight 审计数据检查。

### `record.log`

AgentSight `record` 监控器的运行日志。重点查看：SSL 探针是否挂载、是否发现静态链接 SSL、监控时长、API 调用数、Token、exec 数、文件数和网络端点数。出现 `Recorded ... to session.db` 才说明数据库落盘流程完成。

### `raw-stream.log`

原始 process/debug 事件流，通常是 JSONL。它记录 `EXEC`、`EXIT`、`FILE_OPEN` 等事件、PID、PPID、命令、文件路径、退出码和时间戳。它是排查“探针到底看到了什么”的原始证据，不应和摘要报告简单相加。

### `db-rows.txt`

由 `inspect-db.py` 读取 SQLite 后生成的表行数摘要。它用于快速判断数据库是否真的有数据：`process_nodes`、`audit_events`、`llm_calls`、`token_usage`、`tool_calls` 和 `network_targets` 应在完整实验中大于 0。

### `report-audit.txt`

AgentSight 对审计事件的可读汇总，包含进程、文件、LLM 事件、状态、PID、目标和摘要。适合检查 Agent 是否被归因到正确进程，以及任务是否正常退出。出现 `orphan_response` 表示捕获到响应但请求/响应关联不完整。

### `report-list.txt`

AgentSight 对指定位置可见的会话数据库列表。如果显示 `No session databases found`，只说明该位置没有额外的 `agentsight-*.db`，不代表 `session.db` 不存在。

### `report-prompts.txt`

模型 Prompt 捕获摘要，包含时间戳、来源进程、模型、Token 和 Prompt 片段。它用于确认模型调用是否被观察到，以及 Prompt 是否成功还原。`prompt` 为 `null` 表示元数据或响应被捕获，但对应请求文本没有还原出来。

### `report-summary.txt`

AgentSight 的会话汇总视图。它可能读取 Agent 原生会话文件，因此 API 调用数和 Token 数可能与 `record.log` 或 `report-token.txt` 不一致。分析本次 eBPF 会话时，以 `session.db`、`db-rows.txt` 和 `record.log` 为主；把此文件视为补充视图。

### `report-token.txt`

按模型汇总输入、输出、缓存读取和总 Token。适合分析上下文成本和模型调用次数。它不是费用账单，最终费用应以服务商账单为准。

### `session.db`

SQLite 结构化主结果。当前实验包含以下表：

| 表 | 记录内容 | 研究用途 |
|---|---|---|
| `audit_events` | 进程、文件和 LLM 审计事件 | 事件时间线与证据链 |
| `llm_calls` | 模型、请求/响应、状态、路径 | 模型调用观测和请求响应配对 |
| `network_targets` | 主机、路径、次数和错误数 | 网络依赖与外部服务观测 |
| `process_nodes` | PID、PPID、命令、退出码 | Agent/子进程归因 |
| `resource_samples` | CPU、RSS 等资源采样 | 运行成本与异常资源分析 |
| `token_usage` | 输入、输出、缓存和总 Token | 成本与上下文分析 |
| `tool_calls` | 工具名、输入输出、时间、关联 PID | 工具错误和责任步骤定位 |

### `session.db-shm`

SQLite WAL 模式的共享内存辅助文件，用于锁和并发协调。不能单独分析，读取数据库时应与 `session.db` 放在同一目录。

### `session.db-wal`

SQLite 的预写日志文件。实验正在运行或异常退出时可能含有尚未合并的数据；实验结束后应保留它并与 `session.db` 一起复制。大小为 0 通常表示没有待合并写入。

## 三 重复运行方法

### 1. 准备环境

必须在 WSL2/Linux 中运行，不能在 Windows 原生 PowerShell 或 Git Bash 中运行，因为 AgentSight 依赖同一 Linux 内核中的 eBPF。

```bash
cd /mnt/c/Users/mobao/Desktop/论文方向/lab/agentsight/source/thesis_adapter/test
```

确认以下条件：

- `uname -s` 输出 `Linux`；
- `sched_process_exec` tracepoint 存在；
- 当前用户有加载 eBPF 所需权限；
- `claude` 和 `agentsight` 可执行；
- `.env` 中已经设置 `ANTHROPIC_AUTH_TOKEN`；
- `ANTHROPIC_BASE_URL`、`ANTHROPIC_MODEL` 与本次实验记录一致。

真实密钥只放在本地 `.env`，不要复制到 `results`，不要提交 Git。

### 2. 运行端到端实验

```bash
./run-test.sh
```

脚本会自动：

1. 检查 Linux、tracefs、debugfs 和权限；
2. 读取 `.env`；
3. 清理测试脚本目录下的 `out/` 和 `workspace/`；
4. 启动 AgentSight `record` 和原始 process stream；
5. 运行 Claude Code，只允许 `Write` 和 `Read`；
6. 将报告写入 `out/`；
7. 使用 `inspect-db.py` 生成 `db-rows.txt`。

注意：脚本第 3 步会删除该实验脚本目录下的旧 `out/` 和 `workspace/`。如果要保留旧结果，先复制到带日期的目录，例如：

```bash
cp -a out "../../../../results/runs/$(date -u +%Y%m%dT%H%M%SZ)"
```

### 3. 运行验证

```bash
./verify.sh
```

验证分为四层：

- Tier 1：Claude 返回结果，`hello.txt` 内容正确；
- Tier 2：进程树、审计事件和 Agent exec 被捕获；
- Tier 3：LLM 调用、Token、模型名和 Prompt 被捕获；
- Tier 4：工具调用和网络端点被捕获。

完整成功条件是：

```text
passed 13, failed 0
```

## 四 失败时的排查顺序

1. `claude-run.log` 没有 `result`：先检查模型、端点和 API key。
2. `hello.txt` 不存在：检查 Agent 是否运行在脚本的 workspace 中。
3. `process_nodes=0` 或 `audit_events=0`：检查 tracefs、debugfs、root 权限和 WSL2 内核。
4. `llm_calls=0`：检查静态链接 SSL 自动发现和 `record.log` 中的 BoringSSL attach 日志。
5. `tool_calls=0`：检查 Claude 是否确实使用了 Write/Read，是否修改了允许工具列表。
6. `network_targets=0`：检查请求是否走了预期端点以及网络是否可用。
7. 有 `orphan_response`：说明 TLS 事件捕获到了响应，但请求/响应关联仍不完整；保留原始日志，不要把它当成完整配对样本。

## 五 结果解释边界

本实验验证的是 AgentOps 观测链路，不是多智能体故障归因准确率实验。一次成功的 Claude Code 任务只能证明观测工具捕获到了运行证据，不能证明：

- AgentSight 已经能够识别责任 Agent；
- AgentSight 已经能够定位根因步骤；
- Prompt 捕获内容等于模型内部真实推理；
- Token 统计等于最终账单；
- 该结果可以代表所有 Agent 框架。

后续故障归因实验应在此输出基础上构造可重复失败，并为每次失败记录责任 Agent、责任步骤、根因类型和证据时间区间。

## 六 建议的结果归档方式

每次成功运行后，建议按 UTC 时间保存完整目录：

```text
results/
└── runs/
    └── 20260921T120000Z/
        ├── record.log
        ├── raw-stream.log
        ├── claude-run.log
        ├── report-audit.txt
        ├── report-prompts.txt
        ├── report-token.txt
        ├── report-summary.txt
        ├── db-rows.txt
        ├── session.db
        └── workspace/
```

归档前先脱敏 `session.db`、日志、Prompt、路径、模型调用记录和任何 API 认证信息。`session.db-shm` 与 `session.db-wal` 如果存在，也应和对应的 `session.db` 一起归档。
