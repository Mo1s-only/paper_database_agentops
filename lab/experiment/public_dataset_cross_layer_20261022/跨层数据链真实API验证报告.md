# 公开数据集派生任务的跨层数据链验证

日期：2026-10-22  
状态：3 个数据集家族各 1 个真实 API 回放样本，完成采集与关联检查  
运行目录：`lab/experiment/public_dataset_cross_layer_20261022/`

## 结论

**VERIFIED（限定范围）**：AgentTrace、Who&When、TRAIL 三个数据集家族各选 1 个样本，将不含 gold 标签的数据集内容构造成短任务输入；在 Ubuntu WSL 中由 Claude Code + DeepSeek 执行同一个受控 Bash probe，同时运行 AgentSight recorder 和 eBPF process observer。三次运行都采到原生 Agent 工具事件、AgentSight 的 LLM/tool/token 结构化行和 eBPF 进程/审计事件；Adapter 的 `session-and-tool` 精确对齐为 3/3 accepted。可选的受控 hook 将原生工具 ID 注入带标记的 Bash wrapper 后，沿 eBPF PID 父子谱系逐条关联为 3/3 accepted。

这证明的是：**这条运行时采集与 adapter 数据链可以处理来自三种公开数据集家族的任务输入**。它不是原 benchmark 执行环境的复现，不是历史数据集 span 与当前进程的回连，也不是根因/责任归因准确率。

## 方法与证据边界

每次仅调用 1 个 Claude Code session、1 次 Bash 工具调用；Claude 的原生 stream 作为 `app_log`，AgentSight SQLite 作为 `raw_observation`，AgentSight/eBPF 的进程事件和受控 hook 事件保留来源定位。Adapter 在不知道 gold 标签的条件下构建应用事件，并比较 session+tool 共享 ID；独立的 controlled-instrumentation profile 检查 hook ID、AgentSight tool ID 和 eBPF 进程谱系。

为避免标签泄漏，AgentTrace 回放输入剔除 `root_cause_node_id`、`error_node_id`、`causal_path`、`is_bug_point`、bug 描述和 bug 类型；Who&When 仅使用任务问题及有限历史，不复制 `mistake_agent`、`mistake_step`、`mistake_reason` 或答案标签；TRAIL 仅用 trace/span 结构与属性名，不把 annotation errors、证据文本或属性值送入任务输入。源文件 SHA-256 与回放输入 SHA-256 写在各运行目录的 `dataset-provenance.json`、`capture-summary.json` 中。

### 运行结果

| 数据集样本 | Claude 原生工具 | AgentSight SQLite（LLM / tool / token） | eBPF 系统数据（process nodes / process audit / exec） | Adapter session+tool | 受控 tool-ID→eBPF 谱系 | CLI 费用 |
|---|---:|---:|---:|---:|---:|---:|
| AgentTrace `cod_034b23` | 1 | 2 / 1 / 2 | 36 / 75 / 39 | 1/1 accepted | 1/1 accepted | $0.0196464 |
| Who&When `99da66d8…de09` | 1 | 2 / 1 / 2 | 36 / 75 / 39 | 1/1 accepted | 1/1 accepted | $0.0239176 |
| TRAIL GAIA `0035f455…d34` | 1 | 2 / 1 / 2 | 36 / 75 / 39 | 1/1 accepted | 1/1 accepted | $0.0202904 |
| **合计 / 通过率** | **3** | **6 / 3 / 6** | — | **3/3 accepted** | **3/3 accepted** | **$0.0638544 ≈ ¥0.638544** |

人民币换算沿用实验规划率 ¥10/USD，仅用于预算管理，不是实时汇率或供应商账单。三次均未自动重试，CLI 声明的单会话 `$0.025` 是软上限而非供应商侧硬限额；已报告的新增费用总额低于用户授权的本批次 ¥1 上限。更早的累计账目仍未与供应商账单核销，不在本次增量费用合计内。

### 可复核产物

- AgentTrace：`dataset-20261022-agenttrace-01/capture-summary.json`、`alignment-inputs/real-alignment-comparison.json`、`alignment-inputs/controlled-instrumentation/controlled-instrumentation-report.json`
- Who&When：`dataset-20261022-whoandwhen-01/capture-summary.json`、对应的 Adapter 和受控 profile 报告
- TRAIL：`dataset-20261022-trail-01/capture-summary.json`、对应的 Adapter 和受控 profile 报告
- 每个目录保留 `session.db`、`raw-stream.log`、`claude-agent-a.log`、hook events、PID/process audit 和输入来源哈希。
- 执行器：`my_paper_coding/trace_adapter/capture_public_dataset_replay.py`；probe：`public_dataset_runtime_probe.py`；别名安全启动：`api_key_vault.ps1 -Action RunDatasetReplay`。

## 解释：两种“关联”不能混为一谈

1. **通用 Adapter 语义关联**：Claude 原生 `tool_call_id` 与 AgentSight `tool_calls.tool_call_id` 相同；并由同一应用 session 对应 AgentSight LLM session/PID。此项 3/3 accepted，不依赖 hook 改写 AgentSight 行为。
2. **工具调用到具体子进程的直接桥接**：当前额外启用 PreToolUse hook，把该 tool ID 写进一个受控 Bash wrapper 的 argv，再用 eBPF EXEC 的 PID/PPID 谱系连接被 probe 启动的 Python 子进程。此项也是 3/3 accepted，但它是**显式受控插桩证据**；不能宣称 AgentSight 被动采集天然在进程事件上携带 Claude tool ID。

两类关系均不输出责任或因果结论。当前同一 probe 固定成一个 Bash 调用，能够验证三个输入来源的捕获兼容性，但不能证明不同工具类型、不同 Agent 框架、并发和复杂失败传播下的完整泛化。

## 执行偏差与验证

AgentTrace 的真实请求和采集已成功，初次后处理因空 `parsed/` 目录被重复创建而报错；没有重发 API 请求。修复为可恢复的离线 finalize 后，使用同一批原始 artifact 完成解析和关联。该次 CLI 费用仍按已有原生结果计入，未重复计费。

**VERIFIED**：新增输入隔离测试 2/2 通过；`trace_adapter` 全量回归 137/137 通过；PowerShell API vault 脚本 AST 语法检查通过。`git diff --check` 对本次新文件没有格式错误；输出中另有一个旧实验报告首行尾随空格告警，未改动该历史文件。

## 下一道研究关口

下一步应把每个家族扩成多个独立样本，并加入不同工具类型（至少 Bash 与文件/网络工具），预先固定每个样本的期望工具轨迹和失败标签，再分别报告：采集完整率、原生 ID 对齐率、hook→PID 谱系率、不同观测器版本的失败位置。另需做**不启用 hook**的对照，评估被动 AgentSight 数据能达到哪一层；原因归因的准确率需独立盲标/冻结真值，不能从本轮的 capture pass rate 推导。
