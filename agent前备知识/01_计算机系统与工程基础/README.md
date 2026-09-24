# 第 1 章：计算机系统与工程基础

本章正文：[详细教程](详细教程.md)；学习后完成：[练习与验收](练习与验收.md)；最后对照：[练习与验收答案](练习与验收答案.md)。

## 本章定位

Agent 最终运行在操作系统、进程、文件、网络和数据库之上。AgentOps 要把高层“意图”与底层“实际副作用”关联起来，因此这些基础不是旁支，而是系统级证据的语言。

## 学习目标

- 理解进程、线程、PID/PPID、退出码和进程树。
- 理解文件描述符、标准输入/输出、文件读写和权限。
- 理解 HTTP 请求/响应、流式响应、TLS、代理和网络端点。
- 理解关系数据库、主键/外键、事务、WAL、索引和 SQL 查询。
- 理解时钟、时间戳、并发、竞态、重试、幂等和最终一致性。
- 会在 Windows + WSL2 + Linux 边界中定位路径、内核和权限问题。

## 核心知识

### 1. 进程与因果线索

父子进程关系提供“谁启动了谁”的结构证据，但它不是完整因果关系。相同 PID 只在有限生命周期内有效，跨运行必须结合 `run_id`、时间和命令信息。

### 2. 网络与请求—响应

Agent 调用模型或远程工具时，证据可能分散在应用日志、HTTP/TLS 流、客户端线程和服务端响应中。仅凭“最近时间戳”配对会在并发、流式返回和重试时出错。

### 3. SQLite 与实验数据

SQLite 的 `session.db` 是本项目的重要结构化证据源。要理解表、行、关联键以及 `-wal`/`-shm` 文件，避免把摘要报告当成唯一真相源。

### 4. Linux、WSL2 与 eBPF 前置

eBPF 依赖 Linux 内核、tracefs/debugfs、权限和探针挂载。Windows PowerShell 可以编排实验，但底层采集必须发生在同一 Linux 内核中。

## 项目内材料

优先读：

- [AgentSight 输出数据说明](../../lab/agentsight/results/AgentSight输出数据说明.md)
- [AgentSight 快速复现](../../lab/agentsight/快速复现AgentSight.md)
- [AgentSight 会话说明](../../lab/agentsight/docs/agent-session.md)
- [Snapshot schema](../../lab/agentsight/docs/snapshot-schema.md)
- [进程视图模型](../../lab/agentsight/docs/design/view-session-process-model.md)

按需读：

- `lab/agentsight/docs/design/opentelemetry_setup.md`
- `lab/agentsight/docs/design/memory-cpu-monitoring.md`
- `lab/agentsight/source/thesis_adapter/bpf/README.zh-CN.md`

## 常见误区

- “进程退出码为 0”不等于任务语义成功。
- “Agent 报告写入文件”不等于文件副作用真实发生。
- “捕获到 response”不等于已经捕获并配对 request。
- “报告里的 Token”不一定等于服务商最终账单。

## 本章完成标准

能从 `process_nodes`、`audit_events`、`llm_calls`、`tool_calls`、`network_targets` 和 `token_usage` 解释一次 Agent 任务发生了什么，并指出哪些关联是直接证据、哪些只是推断。
