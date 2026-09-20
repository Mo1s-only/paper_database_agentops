# AgentSight 实测报告：观测 Claude Code（DeepSeek 后端）

**结论：通过。13/13 项断言全部成立，可重复复现。**

AgentSight 在不使用 SDK、不架设代理、不做厂商集成的前提下，完整捕获了一个真实
AI agent 的运行：进程 exec、文件写入、工具调用、以及模型调用的 prompt 原文与
token 统计。

- 测试日期：2026-09-14
- 测试位置：本机 WSL2（`LAPTOP-5CDUGBBT`）
- 测试脚本：[run-test.sh](run-test.sh) / [verify.sh](verify.sh)
- 原始产物：[out/](out/)

---

## 1. 环境

| 项目 | 值 |
| --- | --- |
| 平台 | Windows 10 (19045) + WSL2 |
| 内核 | `6.18.33.2-microsoft-standard-WSL2` |
| CPU | 16 核 |
| AgentSight | 1.0.31（官方预编译 `agentsight-x86_64`） |
| 被测 agent | Claude Code 2.1.270 |
| 运行时 | Node.js v22.14.0 |
| 模型后端 | DeepSeek `deepseek-v4-pro` |
| API 端点 | `https://api.deepseek.com/anthropic`（Anthropic 兼容） |

**为什么必须用 WSL2**：AgentSight 依赖 eBPF，需要 Linux 内核，Windows 原生无法运行。
且 eBPF 只能看到同一内核内的进程，因此被测 agent 也必须运行在 WSL2 内 —— Windows 侧
的进程对它不可见。

---

## 2. 测试内容

让 Claude Code 执行一个会产生真实系统副作用的最小任务：

> 在当前目录创建 `hello.txt`，内容为 `AgentSight test`，然后读回并报告内容。

该任务足以产生三类可观测行为：文件写入（系统边界效果）、工具调用（Write/Read）、
模型调用（含 prompt 与 token）。

启动方式（见 [run-test.sh](run-test.sh)）：

```bash
agentsight record -c claude --db session.db --no-server &   # 先起监控
sleep 2
claude -p "<上述任务>" --allowedTools "Write" "Read"        # agent 在监控窗口内运行
```

Agent 仅被授予 `Write` 和 `Read` 两个工具，无 Bash、无网络。

---

## 3. 结果

### 3.1 断言结果 —— 13/13 通过，退出码 0

```
-- tier 1: the agent really ran, and had a real effect on the filesystem
  PASS  [run] claude produced a result
  PASS  [effect] hello.txt written by agent

-- tier 2: eBPF process / exec / file capture
  PASS  [ebpf] process tree captured (process_nodes=12)
  PASS  [ebpf] audit trail captured (audit_events=30)
  PASS  [ebpf] agent exec attributed to claude
  PASS  [ebpf] record reports non-zero execs

-- tier 3: TLS / LLM capture (model, prompt, tokens)
  PASS  [tls] LLM calls captured (llm_calls=3)
  PASS  [tls] token usage captured (token_usage=3)
  PASS  [tls] model name captured
  PASS  [tls] non-zero token counts
  PASS  [tls] prompt text captured

-- tier 4: tool calls and network
  PASS  [tools] tool calls captured (tool_calls=2)
  PASS  [net] network endpoints captured (network_targets=2)

passed 13, failed 0
```

断言分四层，因为文件效果、进程捕获、TLS 捕获来自不同的探针 —— 分层才能在部分失败时
指出是哪一层断了。

### 3.2 捕获总量

AgentSight 单次运行的汇总输出：

```
Recorded 16s to session.db
4 API calls · 116.6k tokens · 12 execs · 2 files · 2 network endpoints
```

会话数据库 `session.db` 落库情况（7 张表，67 行）：

| 表 | 行数 | 含义 |
| --- | ---: | --- |
| `audit_events` | 30 | 审计事件流 |
| `llm_calls` | 3 | 模型调用 |
| `network_targets` | 2 | 网络端点 |
| `process_nodes` | 12 | 进程树节点 |
| `resource_samples` | 15 | 资源采样 |
| `token_usage` | 3 | token 统计 |
| `tool_calls` | 2 | 工具调用（Write + Read） |

数值由 [inspect-db.py](inspect-db.py) 直接读 SQLite 得出，不经报告层格式化，作为独立于
报告输出的地面真值。

### 3.3 模型调用与 token

`agentsight report token`：

```
group                                   input       output    cache_new   cache_read        total    calls sessions
deepseek-v4-pro                         45058          456            0        71088       116602        4        1
```

### 3.4 Prompt 原文捕获

`agentsight report prompts` —— 这是本题最核心的证据：AgentSight 通过 TLS uprobe
还原出了模型调用的 prompt 内容与规模：

```
timestamp_ms    comm             model                          tokens prompt
1789366691100   HTTP Client      deepseek-v4-pro                 19529 null
1789366690005   HTTP Client      deepseek-v4-pro                 19458 null
1789366688022   HTTP Client      deepseek-v4-pro                 19314 null
1789366680259   claude           deepseek-v4-pro                 58301 Create a file named hello.txt in the current directory containing exactly the line: AgentSigh...
```

首条为初始 prompt（58301 tokens，含系统提示与工具定义），其余三条为后续轮次的
请求。`comm` 列区分了调用来源：`claude` 为主进程，`HTTP Client` 为 Bun 运行时的
网络线程。

### 3.5 进程与文件影响

`agentsight report audit` 节选：

```
timestamp_ms    type       pid    comm           status     summary
1789366691133   process    348    claude         success    exit code 0 (11867ms)
1789366691133   file       348    Bun Pool 5     observed   /root/.claude/projects/.../edd0ebe2-....jsonl
1789366680259   llm        -      claude         observed   Create a file named hello.txt in the current directory...
1789366679733   process    375    claude.exe     failure    exit code 1 (41ms)
```

agent 主进程 pid 348 被完整归因：执行耗时 11867ms、退出码 0。

被观测 agent 的实际副作用（工作区文件）：

```
$ ls -la workspace/
-rw-r--r-- 1 root root 16 hello.txt
$ cat workspace/hello.txt
AgentSight test
```

即：AgentSight 看到的文件路径与 agent 真实写入的文件一致。

---

## 4. 过程中发现的 WSL2 障碍（已在脚本中绕过）

这两点是本次测试的主要技术产出。二者都会导致**静默失败**——探针看似正常挂载，
但会话数据为空。复检脚本：[diagnostics.sh](diagnostics.sh)。

### 4.1 WSL2 默认不挂载 tracefs

libbpf 需要通过 tracefs 解析 tracepoint 的 perf event ID。未挂载时所有探针附加失败：

```
libbpf: failed to determine tracepoint 'sched/sched_process_exec' perf event ID: -ENOENT
libbpf: prog 'handle_exec': failed to auto-attach: -ENOENT
Failed to attach BPF skeleton
```

该报错容易误导：内核本身是完好的（`CONFIG_BPF_SYSCALL=y`、`CONFIG_BPF_EVENTS=y`、
无 lockdown、27 个 sched tracepoint 齐全，ftrace 也能正常抓到 `sched_process_exec`），
缺的只是 tracefs 这个查找路径。`run-test.sh` 每次运行前重新挂载——挂载不跨 WSL 重启
保留。

### 4.2 `record` 的启动模式在 WSL2 下捕获不到数据

`agentsight record -- <命令>`（启动模式）表现出一种很有迷惑性的失败：

- 探针正常加载——`sslsniff` / `stdiocap` / `process` 三个 helper 各持有 24 / 12 / 20 个
  `bpf-prog` fd，说明已通过内核校验器
- 目标进程正常 exec
- 但**数据库中事件为零**，连 `echo` 这种最小命令都抓不到

排查路径：`agentsight debug process`（原始事件流，无会话过滤）在同一内核上能完整输出
EXEC / FILE_OPEN / EXIT 事件，证明 eBPF 层本身健康，丢失发生在**启动模式的会话归属**
环节。进一步对比确认：

| 调用方式 | 落库结果 |
| --- | --- |
| `record -- <命令>`（启动模式） | 0 条事件 |
| `record -p <PID>`（按 PID 附加） | 0 条事件 |
| `record -c <comm>`（按进程名附加，**先起监控再启 agent**） | 正常落库 |

因此测试脚本采用官方文档推荐的 `agentsight record -c claude` 流程，并在启动 agent
之前先起监控。注意事件顺序是必要的：先起监控，agent 的 exec 及其后所有系统调用才
落在捕获窗口内。

---

## 5. 已知限制

- **`report summary` 会回退到 agent 原生会话**。执行 `report summary` 时输出
  `Warning: No agentsight-*.db session database found ...; using local agent sessions.`，
  它转而读取 Claude Code 自身的会话 JSONL，统计的是**历次累计**而非本次捕获。因此
  `verify.sh` 的断言基于数据库行数与 `report token` / `prompts` / `audit` 三个 DB 子命令，
  不依赖 `summary`。

- **BoringSSL 警告属正常现象**。Claude Code 2.x 是 Bun 编译的原生二进制，内嵌
  BoringSSL 且符号表被剥离：

  ```
  libbpf: elf: 'SSL_write' is 0 in symtab ...: try using shared library path instead
  BoringSSL byte-pattern detected in claude.exe. Attaching by offset...
  ```

  AgentSight 会识别 BoringSSL 字节特征并按偏移附加，LLM 捕获实际成功（见 3.3、3.4）。

- **`[claude-code:unrecognized_model]` 为无害提示**。DeepSeek 提供的
  `deepseek-v4-pro` / `deepseek-flash` 不在 Claude Code 内置模型表中，仅打印提示，
  调用正常。

- **测试范围有限**。单次运行、单一模型、单一任务、单机环境。结论适用于验证
  「AgentSight 能观测 Claude Code 这一基本命题」，不构成性能或稳定性评估。

- **未覆盖服务端部署**。代码已同步至 `yj2025@gpu2.solelab.tech:~/agentsight`
  （965M，含完整 `.git`），但服务端尚未执行本测试。该机 `sudo` 需密码而 eBPF 必须
  root，且无法访问 Docker Hub，需先解决权限或准备本地镜像。

---

## 6. 复现步骤

```bash
# 在 WSL2 内
cd /mnt/c/Users/mobao/Desktop/agentsight/test
cp .env.example .env     # 填入 API key；.env 已被 git 忽略
./setup.sh               # 安装 Node.js 与 Claude Code（幂等）
./run-test.sh            # 执行测试并产出 out/ 下的全部产物
./verify.sh              # 断言，失败时退出码非 0

./smoke.sh               # 可选：仅验证 Claude Code → DeepSeek 通路
./diagnostics.sh         # 可选：复检第 4 节的两项内核/模式前提
```

### 产物清单（`out/`）

| 文件 | 内容 |
| --- | --- |
| `session.db` | 会话数据库，全部捕获的原始落库 |
| `record.log` | record 运行日志与汇总行 |
| `raw-stream.log` | 原始事件流（无会话过滤），排查用 |
| `report-{summary,token,prompts,audit}.txt` | 四类报告输出 |
| `db-rows.txt` | 数据库行数地面真值 |
| `claude-run.log` | Claude Code 的 JSON 输出（含 token 用量） |
