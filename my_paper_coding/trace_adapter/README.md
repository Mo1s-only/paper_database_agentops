# Trace Adapter 输入索引与候选对齐（v0.6）

2026-10-22 当前实验进展：`error-propagation-v1` 与 `routing-error-v1` 各完成一个真实双 Agent run，Claude/AgentSight 工具 ID 均 4/4 精确匹配，通用 `session-and-tool` 对齐均 accepted 4/4；受控 hook ID→eBPF 进程谱系只对两次 Bash 调用/场景提供直接插桩证据，Write 工具没有 hook PID 桥。两个单例 scenario attribution 均命中预冻结真值，但不能据 n=1 宣称泛化。新增独立 `controlled_instrumentation` Adapter profile：run45/run46 各为 Bash 2/2 accepted、Write 2/2 abstain；通用 `process-and-tool` 仍 4/4 abstain，默认规则未改变。profile 保留 hook/native/AgentSight SQLite/eBPF 行号与 SHA-256，不宣称被动 AgentSight 自带 tool ID，也不作责任/因果判断。零 API shell/eBPF 边界探针发现嵌套 Bash 会丢失外层非导出函数与 `pipefail`/`errexit`，hook 继续限制到独立白名单 Python 命令。详见[阶段实验报告](../../lab/experiment/experiment_20261021_24_agentsight_candidate_mock/AgentSight_tool_calls_缺失修复验证_2026-10-21.md)。

公开数据小样本兼容性检查见 [`public_dataset_generalization_20261022`](../../lab/experiment/public_dataset_generalization_20261022/数据集选择与适配性说明.md)：只读抽取 AgentTrace、Who&When、TRAIL 共 5 个实例，验证图结构、Agent/step 标签和 span 多错误标注三种输入形态。它不包含本项目的 Claude tool ID/AgentSight/eBPF 运行数据，不能作为端到端关联泛化结果。

公开数据集离线标签映射评估由 [`evaluate_public_dataset_mapping.py`](evaluate_public_dataset_mapping.py) 执行，证据边界见 [`public_dataset_generalization_20261022_trace_join`](../../lab/experiment/public_dataset_generalization_20261022_trace_join/数据集选择与适配边界.md)：AgentTrace 3/3 路径节点和 2/2 路径边可解析；Who&When 两例 gold 字段齐全但缺稳定 turn/step ID；TRAIL 的 GAIA 3/3、SWE-bench 8/8 标注位置命中 span ID，43/43 条历史 span 被规范化。现有 `align_candidates` 按设计拒绝这 43 条历史记录作为当前运行观测（0 admitted / 43 excluded），因此这些结果只支持隔离的公开语义数据兼容性检查，不含 OS PID/eBPF，也不是本项目的当前运行采集或归因准确率。

预算审计发现 run13–46 共 34 次运行报告费用 $0.7774680，未进入 through-run12 账本；本轮 API 调用为 0。逐次费用、摘要哈希及对账边界见[费用审计](../../lab/experiment/public_dataset_generalization_20261022_trace_join/real-api-budget-reconciliation-20261022.json)。

原生 PID namespace 身份实测见 [`experiment_20261013_13`](../../lab/experiment/experiment_20261013_13/README.md)：同一 EXEC 事件记录 initial namespace PID 1791 与 collector namespace PID 34，用户态 PID 也是 34，因此映射由间接 `inferred` 提升为内核直接 `accepted`。同一事件保存 1 ns 的非零时钟不确定度下界。分析器、统一事件 v0.2 和 schema 已接入该证据，Trace Adapter 101/101 测试通过。真实双 Agent API 阶段受 2.00 USD 硬停止线阻止，本轮网络调用为 0。

归因前可查询证据包见 [`experiment_20261013_10`](../../lab/experiment/experiment_20261013_10/README.md)：吸收 RCACopilot 的可组合 handler、OpenRCA 的程序化查询、Watson 的调用条件检查和 OpenRCA 2.0 的逐关系收据。一次真实六事件流生成 5 个可重放查询和 3 条观察关系，5/5 查询哈希一致；PID 关系保持 inferred，严格时间关系和所有归因结论保持关闭。新增 model invocation context v0.1，只保存模型参数、请求/响应配对和提示词/schema 哈希，缺字段时拒绝重建。

归因前统一输入门见 [`experiment_20261012_16`](../../lab/experiment/experiment_20261012_16/README.md)：两个并发 namespace 的内层 PID 都为 1，外层 PID 分别为 14 和 15；namespace+NSpid 可 accepted，仅 local PID 时必须 abstain，历史 Claude 间接证据保持 inferred。真实六事件流字段完整率为 114/114，工具捕获为 1/1。当前允许构建身份/工具关系图，但历史 0 ns 不确定度使严格有界时间排序保持关闭。

观测模块严格质量门见 [`experiment_20261012_15`](../../lab/experiment/experiment_20261012_15/README.md)：同一真实输入两次回放字节一致，8/8 无效协议场景被拒绝；真实会话映射覆盖率按 session 统计为 accepted=0、inferred=1、abstain=0，并明确不将覆盖率当作准确率。本地受控 PID namespace 另以 `NSpid=[13, 1]` 建立一条直接真值并标为 accepted。AgentSight 时钟不确定度已加入系统时钟分辨率下界，新的 release 二进制已经离线构建，但尚未用新的 API 会话验证。

最新真实闭环见 [`experiment_20261012_14`](../../lab/experiment/experiment_20261012_14/README.md)：修复 SSE 对 `_agentsight_clock` 的透传后，真实工具记录保存了 observer boot-relative 时间、boot epoch 锚点和不确定度字段；协议 v0.2 生成 6 条闭合事件并通过严格读取校验。应用 PID 81 与观测器 PID 1758 的对应关系仍标为 `INFERRED`。全仓去重成本为 2.183708 USD，后续停止 API 调用，使用这条真实事件流做离线 provenance/responsibility graph 构建。

离线扩样首版由 [`generate_alignment_stress_fixtures.py`](generate_alignment_stress_fixtures.py) 生成 1,000 条确定性合成身份关联 fixture，落盘于 [`fixtures/alignment_stress_1000.jsonl`](fixtures/alignment_stress_1000.jsonl)。它用于验证 fail-closed fixture oracle，不运行生产对齐器，也不能用来报告真实捕获率或归因准确率；API 调用为 0。新增测试覆盖生成结果和类别分布。

框架原生事件、进程和时钟的真实联合实测已记录到 [`lab/experiment/experiment_20261010_14`](../../lab/experiment/experiment_20261010_14/README.md)：原生工具与 AgentSight 1/1 对齐；620 次锚点显示墙钟—单调钟范围宽度 30 微秒；应用 PID 81 和 eBPF 观测 PID 341 为两套命名空间视图。按本地源码的整数秒 boot epoch 转换规则，本次需补偿 413.555968 ms，补偿后的进程开始时间落入 Popen 边界。

4 次真实运行的零 API 聚合诊断已有报告摘要：15 次原生工具调用中 AgentSight 捕获 12 次，3 个缺失 ID 均未出现在 SQLite 任一表。新增 `capture_incomplete` 门控，跨层工具不能一一覆盖时禁止系统层 Edge 完整性结论。摘要说明当前原始运行目录未随工作区提供，结论尚不能从原始日志重算，见 [工具捕获完整性诊断摘要](工具捕获完整性诊断摘要_2026-10-19.md)。

真实跨故障扩展实验已完成：错误传播与路由角色错误各运行一个真实双 Agent case，共 4 个 API 会话。两个单例场景的 fault type、责任 Agent、责任 Step、责任边和传播边均与 API 调用前冻结的真值一致；每个场景原生工具 4 次、AgentSight 工具 3 次，跨层捕获仍有 1 条缺失。当前 50 项测试通过，结论边界与下一闸门见 [真实跨故障扩展实验报告](真实跨故障扩展实验报告_2026-10-10.md)。

后续真实场景采集会额外生成 `observer-lifecycle.jsonl`：记录 AgentSight recorder/debug 的启动、就绪、每个 Agent 会话前后和停止状态，使用墙钟与单调时钟并记录子进程退出码，不保存凭据。它用于区分 observer 生命周期/时序问题；在没有 SSE 原始帧或上游事件记录时，不能据此断言具体解析或 SQLite 写入根因。新增采集逻辑尚未通过真实 API 运行验证。

扩样执行器现以每个双 Agent 场景 2 CNY 为硬上限；默认两次 CLI session 各最多 0.12 USD，按保守规划率 8 CNY/USD 计算，上界为 1.92 CNY。每次运行会记录 CLI 报告成本及规划汇率折算值；这不是供应商最终账单保证。扩样方案和累计预算边界见 [数据链扩样实验计划](../experiment_control/数据链扩样实验计划_2026-10-19.md)。

完整真实进度实验已完成：两个真实 Agent 会话、3 次原生工具调用和 3 条 AgentSight 工具记录全部通过 `session-and-tool` 模式建立关系；失败触发候选为 Agent B 的 Bash 步骤，Agent 级与运行前真值一致。报告、边界和后续闸门见 [完整真实进度实验报告](完整真实进度实验报告_2026-10-10.md)。

最新已执行真实 API 双 Agent canary：原生工具调用 4 次，系统记录 3 次，共享 ID 对齐 3 条，1 条保留缺失；严格进程/时钟模式未通过。当前 41 项测试通过，真实日志报告费用合计 0.062479 USD。执行方式、证据与下一闸门见 [真实应用对齐实验报告](真实应用对齐实验报告_2026-10-10.md)。

后续新增显式应用事件协议、writer、严格解析器与跨层工具身份对齐；当前共 34 项测试通过。接口见 [应用事件协议与对齐说明](应用事件协议与对齐说明.md)，新实验及失败修复记录见 [应用身份对齐实验报告](应用身份对齐实验报告_2026-10-10.md)。该部分已通过合成协议验证，尚未接入真实框架事件采集。

2026-10-10 新增离线候选匹配器、来源一致性审计及 20 项测试。真实数据上的实验与局限见 [候选对齐实验报告](候选对齐实验报告_2026-10-10.md)。本阶段输出统一轨迹草案，不生成责任标签。

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

该检查会读取 SQLite 中的 `llm_calls`、`tool_calls`、`audit_events`、`process_nodes` 等表，统计真实 API 调用、AgentSight 观测和任务工件是否存在。默认 `--require inputs` 只验证文件与记录数量完整性，通过返回 0，失败返回 2；`--require unified-trace` 当前返回 2，因为本脚本不能验证 Agent/Step 对齐。输入检查通过后可以开发候选对齐，但不能直接声称归因可用。默认只输出报告；指定 `--output` 时只允许创建新文件，避免改写历史报告。

## Adapter 的最小输入契约

Adapter 应当对每个 `run.json`：

1. 根据 `artifacts[].category` 读取原始观测和应用日志；
2. 使用应用日志中的会话、Agent、工具和步骤标识，与系统层 PID/TID、时间和网络事件对齐；
3. 把 `task_context` 作为任务对象和输出对象来源；
4. 把 `validator` 作为独立 oracle，只在离线评分阶段使用；
5. 生成新的规范化 `trace.jsonl` 和 provenance/responsibility graph，并保留每条边引用的原始 artifact 路径与事件定位；
6. 对 `warnings` 中的缺失项输出 `unknown` 或 `abstain`，不能用 `derived` 文件反推缺失的原始事实。

规范化脚本已经为现有结果完成了第一轮证据索引，但它不会补造历史上不存在的应用事件、时间戳或关联 ID。要真正消除这些缺口，下一次真实运行必须在同一个 run 目录中同时保存完整应用 JSONL、AgentSight 原始文件、任务 oracle 和运行元数据。

字段和真实记录示例见：[规范化数据格式说明](规范化数据格式说明.md)。该文档使用 `real-canary-20260929-ubuntu24` 的实际输出解释每一种记录类型及其证据边界。

## 完整性和证据边界

`completeness` 记录本次运行是否具备原始观测、应用日志、任务上下文、独立判据和派生结果。`warnings` 是 Adapter 的前置检查结果。`derived_outputs_are_not_ground_truth` 固定为 `true`，避免把之前的人工或 manifest 驱动分析误当成自动归因证据。

当前已有系统侧关联、冲突处理和缺失证据下的 abstention；应用会话到 Agent/Step 的映射仍不具备证据，不代表通用 Trace Adapter 已完成。

## 离线候选对齐与审计

以下命令在仓库根目录执行，仅使用本地文件；输出目录必须尚不存在：

```powershell
$adapterRoot = 'my_paper_coding/trace_adapter'
$adapterRun = 'real-canary-20260929-ubuntu24'
$adapterOut = "$adapterRoot/alignment_runs/my-new-review/$adapterRun"
python "$adapterRoot/align_candidates.py" --manifest "$adapterRoot/structured_runs/failure_pilot/$adapterRun/run.json" --evidence "$adapterRoot/structured_runs/normalized/failure_pilot/$adapterRun/evidence-events.jsonl" --output $adapterOut
python "$adapterRoot/audit_alignment.py" --manifest "$adapterRoot/structured_runs/failure_pilot/$adapterRun/run.json" --evidence "$adapterRoot/structured_runs/normalized/failure_pilot/$adapterRun/evidence-events.jsonl" --output "$adapterOut/audit-report.json"
python -m unittest discover -s my_paper_coding/trace_adapter -p 'test_*.py' -v
```

`align_candidates.py` 校验 manifest 列出的原始输入哈希，仅消费 `observed` 且在 `raw_observation/app_log` 白名单中的记录，不读取 validator 或 derived 工件。输出：

| 文件 | 用途 |
|---|---|
| `candidate-alignments.jsonl` | 关联候选、规则接受状态、依据和来源引用 |
| `unified-trace-draft.jsonl` | 保留原始记录类型的轨迹草案；Agent/Step 未确定时为空 |
| `provenance-graph.json` | 观测关联图，非因果图或责任图 |
| `alignment-report.json` | 输入哈希、分关系覆盖率、证据缺口 |
| `alignment-review-template.jsonl` | 待独立复核表，不能当作已标注真值 |
| `audit-report.json` | 原始 SQLite 一致性核查与受控扰动结果 |

`accepted` 表示规则接受观测关联，不表示真实责任已确认；`uncertain` 表示候选无法唯一确认，`abstain` 表示没有可接受候选。未校准的置信度保持 `null`。同 PID 和相同时间只能作为工具—LLM 的弱候选；响应中结构化工具 ID 可支持更强关联，PID 冲突或重复候选会阻止接受。

审计仅验证进程关联与原始字段一致，不是独立人工标注；Precision/Recall 保持为空。P0 的 HTTP 记录可保留和追溯，本版没有实现 HTTP 请求—响应匹配算法。完整消息缺失时不得从系统记录补造 B1 消息基线。

## 2026-10-22 公开数据集派生任务运行时跨层验证

AgentTrace、Who&When、TRAIL 各 1 个标签隔离样本完成真实 Claude Code/DeepSeek + AgentSight/eBPF 回放。每条均采集原生 tool event、AgentSight LLM/tool/token rows 和 eBPF process events；`session-and-tool` adapter 关联 3/3 accepted。另启用独立的 controlled hook profile，将工具 ID 标记到 Bash wrapper 并沿 eBPF PID 谱系连接 probe 子进程，3/3 accepted。该 PID 桥是显式受控插桩，不是 AgentSight 被动语义。三个真实 session 的 CLI 报价合计 `$0.0638544`（规划汇率约 `¥0.638544`），均在本批次新增 `¥1` 上限内。该实验是三类公开数据派生输入上的捕获/关联 smoke test，不是原 benchmark 重放或因果归因准确率。详见[实验报告](../../lab/experiment/public_dataset_cross_layer_20261022/跨层数据链真实API验证报告.md)。
