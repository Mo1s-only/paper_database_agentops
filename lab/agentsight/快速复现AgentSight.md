# AgentSight 快速复现指南

本指南用于在 Windows + WSL2 上快速重跑已验证过的 AgentSight 端到端实验。实验对 Claude Code 的一次真实 DeepSeek 调用进行 eBPF 观测，并验证进程、文件、LLM、Token、工具和网络证据是否落库。

## 1. 默认环境

一键脚本默认使用：

```text
WSL 发行版：Ubuntu
AgentSight 工程：C:\Users\mobao\Desktop\agentsight
测试目录：C:\Users\mobao\Desktop\agentsight\test
凭据文件：C:\Users\mobao\Desktop\agentsight\test\.env
原始结果：论文方向\lab\agentsight\results\runs\<experiment_id>
结果文档：论文方向\lab\agentsight\results\experiments\<experiment_id>\实验结果.md
```

`Ubuntu-20.04` 不建议用于当前二进制文件，因为其 glibc 版本过低。当前已验证的是 `Ubuntu 24.04` 对应的 `Ubuntu` 发行版。

## 2. 先做无成本预检

在 PowerShell 中运行：

```powershell
cd "C:\Users\mobao\Desktop\论文方向"
.\lab\agentsight\快速复现AgentSight.ps1 -PreflightOnly
```

预检只确认以下条件，不调用模型：

- WSL 发行版存在；
- 当前用户为 root，可加载 eBPF；
- `tracefs` 和 `sched_process_exec` 可用；
- `agentsight` 与 `claude` 在 WSL 中可执行；
- `.env` 凭据文件存在。

脚本只检查 `.env` 是否存在，不会输出 API key。

## 3. 一键运行

```powershell
cd "C:\Users\mobao\Desktop\论文方向"
.\lab\agentsight\快速复现AgentSight.ps1
```

脚本会依次完成：

1. 检查 WSL、eBPF、AgentSight、Claude 和 `.env`；
2. 如果已有 `test/out` 尚未归档，将它作为独立历史实验保存；如果 `session.db` 哈希已存在，则跳过重复归档；
3. 在 WSL 中执行 `test/run-test.sh`；
4. 执行 `test/verify.sh`；
5. 为本次运行生成唯一实验 ID；
6. 将原始结果归档为 `results/runs/<experiment_id>/`；
7. 单独生成 `results/experiments/<experiment_id>/实验结果.md`。

脚本不会将 `.env` 复制到论文仓库。

## 4. 自定义路径

如果 AgentSight 不在默认位置：

```powershell
.\lab\agentsight\快速复现AgentSight.ps1 `
  -Distro "Ubuntu" `
  -AgentSightRoot "D:\path\to\agentsight"
```

`ArchiveRoot` 必须位于 `lab\agentsight\results\runs` 下，`SummaryRoot` 必须位于 `lab\agentsight\results\experiments` 下，避免将实验产物和结论写入其他位置。

每次运行必须创建新的实验 ID，不覆盖也不追加修改之前的 `实验结果.md`。

## 5. 成功标准

终端应最终显示：

```text
passed 13, failed 0
```

并且归档目录至少包含：

```text
claude-run.log
record.log
raw-stream.log
db-rows.txt
report-audit.txt
report-prompts.txt
report-token.txt
report-summary.txt
session.db
run-info.txt
verification.txt
```

关键表 `process_nodes`、`audit_events`、`llm_calls`、`token_usage`、`tool_calls` 和 `network_targets` 应非空。

## 6. 结果边界

`13/13` 通过只能说明 AgentSight 成功捕获了 Agent 运行证据，不代表请求—响应已完整配对，也不代表已完成故障归因。运行后仍应检查 `report-audit.txt` 是否出现 `orphan_response`，以及 `llm_calls.request_body_json` 是否为空。

## 7. 常见问题

### AgentSight 报 glibc 版本不满足

确认脚本使用 `Ubuntu` 而非 `Ubuntu-20.04`：

```powershell
wsl --list --verbose
```

### `sched_process_exec` 不存在

先退出 WSL 后重启：

```powershell
wsl --shutdown
```

然后重新运行预检。脚本会尝试自动挂载 `tracefs`。

### `.env` 缺失

在 `C:\Users\mobao\Desktop\agentsight\test\.env` 中配置：

```text
ANTHROPIC_AUTH_TOKEN=<本地密钥>
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
ANTHROPIC_MODEL=deepseek-v4-pro
ANTHROPIC_SMALL_FAST_MODEL=deepseek-flash
```

不要将 `.env` 、API key 或未脱敏的 prompt/response 提交到 Git。
