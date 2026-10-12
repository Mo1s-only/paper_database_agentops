# experiment_20261010_14｜框架原生事件、进程与时钟实测

## 目标

接入 Claude Code CLI 的原生 `stream-json` 事件，在同一次真实 API 会话中同时记录：

- framework session、tool_call 与原生事件生命周期；
- Claude 启动进程及其子进程树；
- 工具进程自报 PID、PPID、PID namespace 与 `/proc` 启动 tick；
- `CLOCK_REALTIME`、`CLOCK_MONOTONIC`、`CLOCK_BOOTTIME` 配对锚点；
- AgentSight 的 LLM、工具、进程与时间记录。

## 预算

单个真实 CLI 会话，上限 0.10 USD，不自动重试。实验前累计本地 CLI 报告费用为 1.576492 USD，计划上界为 1.676492 USD，低于 2.00 USD 硬停止线。

## 证据状态

- `VERIFIED`：目录、计划与采集字段已在 API 调用前创建。
- `UNVERIFIED`：AgentSight PID 是否能对应到采样进程树、两套时间能否建立有界转换；需由本次实测决定。

原始结果写入 `results/`，该目录受仓库 `.gitignore` 保护；可提交报告只保留必要摘要与哈希。

## 实测结果

- 1/1 个真实 API 会话成功，费用 0.024657 USD；原生 Bash 工具和 AgentSight 工具记录 1/1 对齐。
- 原生生命周期具备 init、tool_use、tool_result、result 各 1 条。
- 620 次时钟配对采样的 `realtime - monotonic` 范围宽度为 30 微秒。
- 应用 PID 为 81，AgentSight PID 为 341。二者不在同一个可见 PID 数字空间；本地 AgentSight 源码的 eBPF 程序使用 `bpf_get_current_pid_tgid`。
- AgentSight 本地源码用整数秒 boot epoch 转换 `bpf_ktime_get_ns()`。本次实测校正量为 413.555968 ms；校正后的 AgentSight 进程开始时间 1791615126130.556 ms，落在应用 Popen 边界 1791615126129.423–1791615126130.928 ms 内。
- 原生 tool_result 接收时间比原始 AgentSight 工具时间晚 1542.488 ms；去除上述整秒误差后为 1128.932 ms，仍包含工具执行和流式传输时间。

详细报告：[实验报告](实验报告.md)，机器可读摘要见 [analysis.json](analysis.json)。
