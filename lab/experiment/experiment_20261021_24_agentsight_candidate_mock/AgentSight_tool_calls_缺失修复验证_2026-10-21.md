# AgentSight `tool_calls` 缺失修复验证

日期：2026-10-21  
目标：定位并修复 DeepSeek Anthropic SSE 响应未投影为 AgentSight `tool_calls` 的问题。  
范围：代码路径、离线回归、真实 DeepSeek/Claude Code canary；未将时间/进程推断冒充为直接工具 ID 对齐。

## 证据与根因定位

- **VERIFIED（历史运行）**：run10/run11/run12 的 Claude 原生日志含工具调用 ID，但对应 AgentSight SQLite 的 `tool_calls=0`；run10/run11 的 LLM 响应体为 `null`。run12 候选二进制哈希不同，不能作为本次修复候选的端到端回归结果。
- **VERIFIED（代码路径）**：AgentSight 要先把 SSL 明文中的 HTTP/2 数据帧组装成完整 HTTP 响应，再解压并解析 SSE，最后由 MaterializedView 从 Anthropic `content_block_start` 提取 tool-use ID。
- **VERIFIED（离线复现）**：HTTP/2 帧跨 SSL 读取边界时需要缓存补齐；SSE 解析必须在 HTTP/2 重组、解压之后。离线单测能以完整响应体生成工具调用、参数、usage。
- **VERIFIED（真实 run15）**：真实 DeepSeek/Claude Code 调用成功（Claude Code 退出码 0），AgentSight 捕获 184 个 SSL 事件：READ 181 次/4264 字节，WRITE 3 次/32779 字节。HTTPParser 输出 2 条 HTTP 响应，但响应体合计 0 字节；HTTP/2 待处理字节峰值为 2808，待处理流和 header block 峰值均为 0。
- **VERIFIED（真实 run15 SQLite）**：2 条 `api.deepseek.com` HTTP 200 LLM 调用；请求体 JSON 长度分别 14708、16011，响应体 JSON 均为 `null`，状态均为 `incomplete / stream_response_body_not_observed`；`tool_calls=0`、`token_usage=0`。网络目标、进程/文件观测和 Claude 原生工具语义均存在，但 AgentSight 没有工具语义行。
- **VERIFIED（诊断器校准）**：第一版新计数器在已知会产生 HTTP/SSE/tool 输出的测试中错误报告全 0。改为共享原子计数后，同一 Anthropic HTTP/2 测试报告 SSL 输入 2（READ 1/809B、WRITE 1/212B）、HTTP response 1/769B。故撤回 run14 “HTTPParser 未收到 SSL 事件”的判断；run15 使用修正后的计数器。
- **INFERRED（尚未区分）**：问题已缩小到“SSL 读取字节 → HTTP/2 DATA 帧/响应体重组”边界，不是完全没有 SSL/eBPF 数据，也不是工具 ID 对齐器单独漏配。run15 保留了请求和响应头，但没有 HTTPParser 响应体。持久化记录未保存 SSL 明文字节，因此尚不能区分探针漏掉关键 read、TLS 事件跨 TID/流键分散、HTTP/2 帧被判为不完整/无效等具体原因。

## 修复与诊断改动

1. HTTP/2 parser 按进程、线程和流向缓存不完整字节，支持跨读取边界补齐帧，并限制待处理缓冲区大小。
2. 分析器顺序改为 `HTTPParser → HTTPDecompressor → SSEProcessor`。
3. Anthropic 工具块按 block index 聚合 `input_json_delta`，保留 tool-use ID 并解析完整参数。
4. 对可识别 LLM endpoint 但缺少请求体的事件保留低置信度记录；成功但未观测到流式响应体的调用标为 `incomplete`，不误报完整。
5. HTTPParser 捕获诊断改用共享原子计数；原诊断实现会在解析器已经生成 HTTP/SSE 事件时仍打印全 0。

## 验证结果

- `cargo test --offline --manifest-path ext/analysis/Cargo.toml --lib --quiet`：133/133 通过。
- Anthropic HTTP/2/SSE 离线单测校准计数器并产出 tool call：通过。
- `cargo build --offline --release --manifest-path collector/Cargo.toml`：release 构建完成，并被 run15 实际执行。
- run15 AgentSight 1.0.31 SHA-256：`1d18617d6e2a66f0aa4e6a0640be3d2a1e282581fe3843f719ebed6106cc05ee`。
- **真实 API run15**：费用 `$0.0203304`，无自动重试；运行 soft cap `$0.05`。累计预算保护按用户在本轮明确要求关闭。
- 规划账本沿用此前累计 `$2.60664`，加 run15 后为 `$2.6269704`（按 `$1=¥10` 为 `¥26.269704`）。历史冻结基线 `$2.183708` 的原始日志仍未完全复核；该规划换算不是供应商账单复核值。
- collector crate 全量 `cargo test` 曾在早前尝试中因首次编译耗时被手动中断；不记为通过。

## 当前结论与下一验证门

**当前还没有修复成功**：真实 API 调用已跑通，SSL/eBPF 和 LLM 请求语义均采到，但 AgentSight 未捕获/重组出响应流体，所以没有 `tool_calls` 与 `token_usage`，严格工具 ID 对齐无从成立。

下一步应在不落盘明文的前提下，扩展诊断为按 PID/TID/方向统计 SSL read、HTTP/2 HEADERS/DATA/CONTINUATION 帧、DATA payload 字节、残留帧长度及 `truncated/bytes_lost`；再分别用本地可控 HTTP/2/SSE 回放和真实 DeepSeek canary 验证。只有 AgentSight `tool_calls` 中出现原生日志中的同一 tool-use ID，且参数/usage 可复核，才算修复成功。

## 2026-10-22 后续排查记录（run16–run24）

本轮继续使用真实 DeepSeek API + Claude Code canary；每次最多 2 个 LLM 调用、无自动重试、CLI soft cap `$0.05`，原始 SSL 明文仍未落盘。run17–run24 的真实调用费用合计 `$0.1711088`；逐次账单值和完整日志见同目录下对应 `real-canary-20261022-N/diagnostic-summary.json` 与 `record.log`。历史费用基线仍未完全复核。

- **VERIFIED（run16）**：SSL 读 280 次/5323 字节、写 3 次/33171 字节，`truncated_ssl_events=0`；HTTP/2 `NeedMore=277`，结束仍有 3864 字节待处理。此时尚未加 HTTP/1 pending 诊断，不能据此断言流量类型。
- **VERIFIED（离线修复）**：新增 HTTP/1.1 `Transfer-Encoding: chunked` 跨任意 TLS 分片重组测试，并贯穿 HTTPParser → 解压器 → SSEProcessor → MaterializedView；成功提取合成 Anthropic `toolu_chunked_1`、工具参数及 usage。全量 `agentsight-analysis` 测试为 134/134 通过。
- **VERIFIED（run17–run18）**：改动后真实流量没有进入 HTTP/2 parser；run18 中 HTTP/1 pending 事件 309 次，HTTP/1 缓冲结束有 5952 字节、1 个 pending buffer，H2 调用为 0。说明合成 HTTP/1 修复本身不足以证明真实链路正确。
- **VERIFIED（run19–run21）**：真实响应头被解析为 HTTP/1 chunked；缓冲残留约 2.9–5.9KB，仍无 HTTP response。内容无关的 chunk framing 诊断在 run20/21 指示 payload 后 CRLF 失配，尚无原始字节证据可以判定是采集丢字节还是响应边界/编码解析问题。
- **VERIFIED（构建链）**：先前单跑 `cargo build --release` 只重建 Rust crate，没有重建 BPF C loader；run23 508/508 个 SSL 事件都没有 `connection_id`，证明此前按连接隔离的改动并未实际运行。WSL 初始也缺 `make/clang/bpftool/libbpf-dev`，且仓库缺失 `libbpf`、`bpftool` 子模块，`vmlinux/x86/vmlinux.h` 是指向 `vmlinux_601.h` 的占位文件。
- **VERIFIED（run24 实际 loader）**：用系统 `clang-21`、`bpftool`、`libbpf.a` 和真实 `vmlinux_601.h` 编译 BPF loader，再同步到 `agentsight-capture/vendor/bpf` 并重建 collector。run24 中 `connection_id_missing_events=0`、不同 TLS connection ID 数为 1，证明新事件字段确实进入真实运行；但 chunk 状态仍为 payload 后 CRLF 失配（offset 878），`http_responses=0`、`tool_calls=0`、`token_usage=0`。因此连接 ID 是有用的正确性改进，但不是此次缺失的充分修复。
- **VERIFIED（run24 环境/语义）**：Claude Code 退出码 0；AgentSight 有 eBPF 系统数据、2 条 LLM 语义记录和 `/anthropic/v1/messages?beta=true` 网络目标；Claude 原生日志能看到工具调用，但 AgentSight 的 tool 与 usage 表仍为空。CLI PID/ eBPF PID 的时间锚点和 namespace 映射已接受，不能把 PID 差异当成当前漏采根因。
- **当前结论**：问题仍未修复成功。已排除“本轮真实调用没有执行”“没有 SSL read”“仅因未关联 TLS connection ID”；尚未证实 SSL ring buffer 丢事件，也未证实 decoder 的 CRLF 逻辑错误。run24 的证据把边界定位在 SSL plaintext 事件字节 → HTTP/1 chunked body 重组；offset 仅是长度信息，不含 payload。

下一 gate：增加每连接 SSL 事件单调序号/缺口计数及 chunk 重组的长度/分段哈希或字节类别校验（不记录 prompt、响应文本或 API key），确认是否有事件丢失/乱序或原始字节到 Rust `data` 转换发生偏差；先用真实捕获边界做离线回放，再跑单次真实 canary。只有真实 AgentSight SQLite 出现 Claude 原生日志同 ID 的 tool-call 行、且 usage 可核对，才判定跨层语义采集恢复。

## 2026-10-22 后续排查记录（run25–run33）

本批次 run29–run34 均为真实 DeepSeek API + Claude Code/eBPF canary，无自动重试、单次 CLI soft cap `$0.05`；逐轮原始记录位于 `real-canary-20261022-29` 至 `real-canary-20261022-34`。六次报告费用合计 `$0.1193616`，这是本批次 CLI 报告值，不是供应商账单核验值。

- **VERIFIED（run25–run28）**：重新编译并同步 BPF loader 后，连接 ID 缺失数为 0、连接数为 1、事件序号无缺口/乱序；SSL 字节无 truncation。run28 HTTP Parser 已重组出 2 个响应、共 6330 body bytes，HTTP/1 pending 最终归零，但 `tool_calls=0`、`token_usage=0`，问题因此位于 HTTP response 到语义投影，而非 eBPF 没采到响应。
- **VERIFIED（run29–run30）**：两个 DeepSeek 200 响应都有完整 body，响应头为 `text/event-stream`，但 HTTP/1 SSE 正文带压缩；旧 SSE 分支虽按响应头接受 payload，后续却仍只凭 `event:`/`data:` 正文标记选择解析。修复该判断后，run30 显示 `Content-Encoding` 存在、正文非 JSON/非明文 SSE、解压未成功，语义表仍为空。
- **VERIFIED（run31–run32）**：真实响应 `Content-Encoding: zstd` 且使用 HTTP/1 chunked framing。HTTP Parser 已将 chunk framing 解掉；HTTPDecompressor 却再次尝试 chunk 解帧。移除重复解帧后，zstd 仍失败。继续追到 HTTP Parser：它把压缩实体字节先经过 `String::from_utf8_lossy`，随后再从字符串重建 `body_hex`，不可解码字节已被替换。这是 zstd 失败的直接原因。
- **修复与离线验证**：HTTP/1 parser 现同时保留精确 `body_bytes` 与用于展示/文本 SSE 的 lossy `body`；`body_hex` 和 `total_size` 均来自精确字节。HTTPDecompressor 不再重复解 HTTP chunk framing；SSE 分支使用 `Content-Type: text/event-stream` 判断并产生不含正文的计数诊断。新增二进制 chunked body 保真与 zstd-after-dechunk 回归测试；`agentsight-analysis` 138/138 单测、2/2 doctest 通过，collector release 构建通过。
- **VERIFIED（真实 run33）**：Claude Code 成功退出，报告费用 `$0.0204144`；HTTPDecompressor 对两条响应分别完成 zstd 解压（输入 2133/608 bytes，输出 22919/3149 bytes），SSEProcessor 解析 176/25 个事件并完成语义事件投影。AgentSight SQLite 中 2 条 LLM 调用均 `complete`，`token_usage=2`（总计 7746 tokens），`tool_calls=1`；Claude 原生日志 1 个 `Bash` tool-use ID 与 AgentSight `tool_call_id` **精确相等**。这是首次真实 canary 证明 SSL/eBPF → HTTP/1 chunked → zstd → Anthropic SSE → tool/token 语义表完整恢复。
- **INFERRED（run33 运行时关联）**：工具语义 ID 与 Claude 原生记录直接严格匹配；但 AgentSight process/eBPF 事件没有该 `tool_call_id`，具体子进程仍只能由命令与时钟窗口得到唯一候选，属于推断，不是语义 ID 到进程 ID 的直接 join。
- **VERIFIED（诊断报告修正）**：run33 旧后处理器仍硬编码“response body 与语义表为空”的历史结论。现已改为按 SQLite 实际行数/响应体及 Claude 原生 tool ID 动态生成；重新分析 run33 得到 `response_bodies_observed=2`、`exact_tool_id_match_count=1`，unverified 仅保留 tool-use 到具体 exec 的无共享 ID 限制。
- **VERIFIED（真实 run34 稳定性复测）**：相同修复候选再次成功，费用 `$0.0186328`；zstd 两条响应均解压成功（1269→9968、765→4560 bytes），SSE 分别解析 76、36 个事件。SQLite 再次得到 2 条 LLM 调用、2 条 usage、1 条 tool call；Claude 原生 1 个 `Bash` tool-use ID 与 AgentSight ID 精确匹配。run34 后处理器确认 `response_bodies_observed=2`、`exact_tool_id_match_count=1`。

**当前结论**：原先长期失败不是 API、Claude Code 语义日志或 eBPF 事件采集本身缺失，而是 HTTP/1 二进制响应在 UTF‑8 转换时损坏，且解压器重复解帧；同时 SSE 的响应头/正文分支不一致也掩盖了解析失败。run33、run34 两轮真实 canary 均恢复了完整的 AgentSight tool/token 语义，并逐轮与 Claude 原生 tool-use ID 精确匹配。尚不能据此声称“所有数据集/服务均稳定”，也不能声称具体 shell 子进程与 tool-use 已直接 ID join。下一 gate 是覆盖一轮不触发工具的普通回答，并在另一数据集/响应格式上验证解压与语义投影；再决定是否需要把 tool semantic ID 与 runtime process 关系从时间/命令推断提升为直接关联。

## 2026-10-22 后续验证：工具语义到 eBPF 子进程（run33–run35）

- **含义澄清**：Claude 原生日志中的 `tool_use.id` 与 AgentSight `tool_calls.tool_call_id` 是同一个协议 ID，因此这两份语义记录可以直接按 ID join。eBPF `EXEC` 事件记录的是 PID/PPID、可执行文件、命令和时间，不包含该协议 ID；所以不能拿 `tool_call_id` 直接查询出某个 PID。此前仅报告“唯一命令 + 时间窗”候选，低估了已经存在的进程谱系证据。
- **分析器改进**：`analyze_ebpf_real_canary.py` 现在为每个候选重建 PID→PPID 祖先链，并检查它是否到达 Claude launcher PID；候选仍须唯一、命令匹配，并落在原生日志 tool-use 与 tool-result 接收时刻之间。新状态 `inferred_unique_lineage_and_tool_window_candidate` 明确表示“进程树和时间窗共同支持的推断”，不冒称直接 ID join。对 run33/run34 的旧原始记录重跑后，两轮都发现 `python3 → bash → claude` 祖先链，且候选数量均为 1。
- **VERIFIED（真实 run35）**：DeepSeek API + Claude Code + AgentSight/eBPF 成功，CLI 报告费用 `$0.0185048`，无自动重试。SQLite 有 `llm_calls=2`、`tool_calls=1`、`token_usage=2`、`process_nodes=33`、`audit_events=121`；响应体观测数为 2，Claude 原生日志的一个 Bash tool-use ID 与 AgentSight ID 精确匹配。候选 `python3` 的 PID/PPID 链是 `869 → 868 (bash) → 740 (claude)`，该 EXEC 的重建时刻位于对应 tool-use/result 接收时间窗内；唯一候选数为 1。
- **结论边界**：当前证据支持较强的“同一 Claude 执行上下文、同一工具时间窗、唯一命令和进程祖先链”关联；足以作为保守的跨层 attribution candidate，并可与语义 tool ID 关联存储。但 eBPF 记录中仍没有 `tool_call_id`，因此在严格数据模型中应保存为 `inferred`（带规则、候选数、祖先链和时钟证据），不能称 `direct/shared-ID`。要把这一段提升为直接关联，下一 gate 是验证 Claude Code hook/runner 能否在 PreToolUse/PostToolUse 边界暴露稳定 invocation ID，并将该 ID 与执行进程 PID 绑定；需检查 hook 是否可观测具体 PID、是否有无工具调用/并发调用时的误配，并用多次真实 canary 与负对照验证。

## 2026-10-22 后续验证：通过 PreToolUse 构建受控共享 ID（run36–run38）

- **VERIFIED（机制依据）**：Claude Code 官方 Hooks 文档说明，`PreToolUse` 输入含 `tool_name`、`tool_input`、`tool_use_id`，并允许通过 `updatedInput` 修改工具参数后再执行。因此可以在受控实验中把同一工具 ID 显式带入运行时边界；此能力来自 Claude hook instrumentation，不是 AgentSight/eBPF 原生提供的字段。[官方 Hooks reference](https://code.claude.com/docs/en/hooks)
- **VERIFIED（run36 失败定位）**：hook 日志已记录同一个 Bash `tool_call_id`，而且记录了命令哈希、未记录原始命令；但把 `export AGENTOPS_TOOL_CALL_ID=...` 加到命令文本后，eBPF 只看到 Claude 启动的 `/bin/bash -c source ...shell-snapshot...`，子进程 Python 的 argv 不含标记。原因是 Claude Code 把 Bash 工具内容写入 snapshot 脚本执行，不把命令文本作为 shell `-c` 的 argv 传递。因此仅改写 shell 命令正文不够。run36 成功完成 2 条 LLM、1 条 tool、2 条 usage 和 35 个 process nodes，费用 `$0.0198224`；tool→process 仍为 lineage/time 推断。
- **修复（受控单命令）**：对本 canary 唯一的 `python3 ...` 命令，PreToolUse hook 将命令改写成 Bash `exec -a 'AGENTOPS_TOOL_CALL_ID=<tool_use_id>' python3 ...`。`exec -a` 将该标记放在 Python 进程自己的 argv[0]，故内核 `sched_process_exec` 能在该 Python PID 的 EXEC 事件中直接观测标记；不依赖 shell snapshot 文件名。hook 仅保存 ID、命令哈希、是否已标记和时间，不记录原始命令。
- **VERIFIED（真实 run37、run38 复测）**：两轮均成功完成 DeepSeek API + Claude Code + AgentSight/eBPF，费用分别 `$0.0204408`、`$0.0189848`，每轮均无自动重试。两轮各有 2 条 LLM、1 条 AgentSight tool_call、2 条 token_usage，并且 Claude 原生日志与 AgentSight `tool_call_id` 精确相等；分析器也在同一唯一 Python 子进程的 eBPF EXEC argv 中找到这个精确 ID。run37 进程 PID 1629；run38 PID 1842；两个进程的 PPID 链均回到对应 Claude launcher。关联状态为 `direct_instrumented_id_lineage`，两次连续复现。
- **准确解释**：这里的“direct”仅指**受控 instrumentation 下的共享 ID join**：Claude hook 提供语义 ID，实验 runner 将 ID 传入 Python exec 的 argv，eBPF 记录该 argv，再用 PID 确定该具体进程。AgentSight 默认/被动采集并不会凭空知道 `tool_call_id`；没有 hook 注入的 run33–run36 仍只能标为 `inferred`。这能为受控 benchmark 提供进程归属 ground truth，但不能直接外推到任意自然运行的 Bash、多进程命令或其他 agent runtime。
- **下一 gate**：如要覆盖任意 shell 命令，应评估 BPF 是否可从 exec 环境中只读取白名单变量 `AGENTOPS_TOOL_CALL_ID`，而不是采集整个环境（后者可能暴露密钥）；再用 compound command、pipeline、后台进程、并发 tool call 和负对照验证传播率及误关联率。若不做这类侵入式 instrumentation，生产 adapter 应继续保留 `inferred` 状态及证据字段，而不是把所有唯一时间窗候选升格为 direct。

## 2026-10-22 阶段收口：受控桥复现与跨数据集验证（run39–run46）

- **VERIFIED（canary 1:N，run39–run42）**：run39/run40 的单工具 ID→单目标进程再次通过；run41/run42 刻意令一个 Bash tool invocation 连续启动两个 Python 子进程，两轮均在同一 tagged ID carrier 的 eBPF 进程谱系下找到 2 个目标 PID，状态均为 `direct_instrumented_id_lineage`。这说明桥接不是“每个 tool ID 只能对应一个进程”的假设，但仍只覆盖受控 Bash compound command。
- **VERIFIED（error-propagation-v1 单步 run43）**：DeepSeek/Claude Code 与 AgentSight/eBPF 真实运行成功，CLI 报告 `$0.0264232`；SQLite 有 `llm_calls=3`、`token_usage=3`、`tool_calls=2`。Claude 原生 2 个 ID 与 AgentSight 2/2 相等；Bash 的 Pre/Post hook 均观察到，eBPF tagged wrapper 与 `scenario_service_observer.py` 执行 PID 可由谱系直接连起。此轮只是 agent_a 单步，不作完整跨 Agent 结论。
- **VERIFIED（run44 部分运行）**：agent_a 成功，费用 `$0.0244112`；原计划含两个 session，但会话间累计硬停止仍生效，未启动 agent_b。该运行保留为部分记录，不计入完整双 Agent 样本。根因是 `--ignore-cumulative-budget` 仅影响启动前门控，未影响 runner 的会话间停止分支；之后已修复为显式覆盖时跳过该历史累计阈值，单次 `$0.05` soft cap 与每批 ¥2 规划上限仍保留。
- **VERIFIED（error-propagation-v1 完整 run45）**：两 Agent 均成功，CLI 报告费用 `$0.0496904`（按本实验规划汇率折算 ¥0.496904；非供应商最终账单）。AgentSight SQLite：`llm_calls=6`、`token_usage=6`、`tool_calls=4`。4 个 Claude 原生工具 ID 与 AgentSight 工具 ID 4/4 精确相等；规范化 `session-and-tool` 为 accepted 4/4，未使用 ground truth 参与对齐。两条 Bash tool ID 各自在 hook Pre/Post 日志和 eBPF tagged EXEC 中出现，并各自连到对应 Python 执行 PID。Write 工具保留语义层 ID，但没有被宣称为单独的 eBPF 子进程直连。
- **VERIFIED（routing-error-v1 完整 run46）**：两 Agent 均成功，CLI 报告 `$0.0533712`（¥0.533712 规划折算）。AgentSight 有 6 条 LLM、6 条 usage、4 条工具记录；原生 ID 与系统 ID 4/4，`session-and-tool` accepted 4/4；两个 Bash tool ID→eBPF 执行谱系均通过。跨数据集 scenario oracle 评分的 fault type、责任 Agent、Step、责任边、传播边均精确命中，观察到任务失败；此处为第二个单例，不是泛化准确率。
- **VERIFIED（零成本负对照 run35）**：对未启用 ID 注入的既有真实 canary 重跑同一 ID→PID 审计，原生/AgentSight semantic tool ID 为 1/1，但无 hook ID、无 eBPF ID carrier，状态是 `semantic_id_only`；原始 canary 后分析器仍将唯一命令+时间窗+PID 谱系结果标为 `inferred_unique_lineage_and_tool_window_candidate`。审计器没有把这条旧式候选升格为 direct。
- **VERIFIED（工程回归）**：trace_adapter 全量 122 项测试通过；新增 analyzer 输出 `tool-id-process-audit.json`，scenario 规范化输出与 attribution score 均保留在各自 run 目录。纯离线交错双 ID fixture 验证两组并发 PID 树不串配，未注入 ID 时两条候选均保持 `semantic_id_only`。run45 一次早期后处理因默认 `alignment-inputs` 已有本轮失败尝试创建的部分目录而停止；未删除/覆盖该目录，改用新目录 `alignment-inputs-tool-bridge` 完成后处理。

### 阶段结论与论文边界

**当前阶段达到受控验证门槛**：两种数据集各一个完整真实双 Agent run 均捕获到 Claude 原生日志、AgentSight LLM/tool/token 语义与 eBPF 系统进程事件；semantic tool IDs 均无缺项，tool↔AgentSight `session-and-tool` 4/4 accepted。hook 注入的 Bash ID 到具体 eBPF 子进程也在两数据集共 4 个 Bash 调用中 4/4 复现。两个场景的冻结真值均被精确恢复，但样本量每种故障仅 n=1。

**不要混淆两种关联结果**：通用适配器的 `process-and-tool` 模式在 run45/run46 仍是 4/4 abstain；这是因为注入 ID 尚未被写入通用对齐器的输入契约。直接 hook→eBPF 证据目前由独立审计 sidecar 记录，且是受控执行改写，不代表 passive AgentSight 原生带有 `tool_call_id`。真实未注入 run35 保持 inferred，正/负条件结果符合预期。

本批 run43–run46 CLI 报告费用合计 `$0.153896`；包含一个明确不完整的 run44；不是 provider invoice 核验。历史累计账本仍有原始日志未完整复核，本轮只按用户此前授权覆盖累计停止线，未修改历史基线。

**下一 gate（新阶段）**：已完成零 API 的 Bash/eBPF 形态、并发进程及负对照验证；尚未完成的是 Claude Code 自身对并发 `PreToolUse` 的调度行为与完整 snapshot 环境等价性。再评估如何将 sidecar 作为 Adapter 中一个明确隔离的 controlled-instrumentation profile；普通生产 profile 继续将无共享 ID 关系保留为 inferred/abstain。更广故障数据集需要多 seed、多样本和盲化标签后才能讨论泛化性能。

## 2026-10-22 下一阶段前置门：零 API shell/eBPF 边界测试

- **VERIFIED（shell 语义对照，0 API）**：`probe_tool_id_bridge_shell_semantics.py` 在 Linux Bash 中比较原始命令与 `exec -a ID bash -c <command>` wrapper。5 类中 2 类一致（导出环境变量、同一命令中的 `cd && pwd`）；3 类出现差异：外层 shell 的非导出函数在内层不可用，外层 `pipefail` 丢失，外层 `errexit` 丢失。该探针是可控 prelude，不等于完整 Claude snapshot，但足以证明“任意 Bash 一律包一层”不应成为默认。
- **修复（收紧 hook）**：将 `wrap-all-bash` 替换为 `allow-known-scenario-scripts`；只允许四个预定义场景脚本以独立 `python3 <script> [args]` 形式出现时改写，带 shell operator 的命令及任意用户 Bash 命令不注入。非 Bash 工具保持 no-op；任意 Bash 没有 `updatedInput`。已完成数据集正是独立 Python 场景调用，因此 run45/run46 原始结论不受本次收紧影响。
- **VERIFIED（AgentSight/eBPF 本地探针，0 API）**：使用 SHA-256 `caa48e699a31c73837c63e581dfab7c47daeddbf09369d5ec83bdcf4c6aa5a76` 的当前 collector，`ebpf-boundary-run2` 观测 22 个 EXEC 事件。pipeline 产生的 Python 与 cat 两个进程均能沿 tagged Bash ID 找到；后台 wait 子进程、两个顺序 Python 子进程、退出码 7 的进程均可关联。两条同时运行的合成 Bash wrapper 分别携带不同 ID，两个 PID 集合无交叉（`concurrent_ids_isolated=true`）。无标记负对照没有 carrier；所有预期退出码一致。
- **VERIFIED（hook 写入并发/质量门）**：新增 16 个并发 hook 子进程写入同一 JSONL 的回归测试，确认 16 条记录均为完整 JSON、ID 无串写；另验证任意 Bash 与 Read 工具不被改写。trace_adapter 全量测试现为 125 项（包括前述两组 analyzer/进程谱系夹具）。
- **证据文件**：shell 语义比较见 `zero-api-tool-id-boundary-20261022/bridge-shell-semantics.json`；实际 eBPF 事件与摘要见同目录 `ebpf-boundary-run1/`、`ebpf-boundary-run2/`；对应代码为 `probe_tool_id_bridge_shell_semantics.py`、`probe_tool_id_bridge_ebpf.py` 与 `test_tool_id_bridge_analyzer.py`。

**结论边界**：这些结果验证的是已观察到的 Linux exec argv/PID/PPID 传播和本地 hook writer 并发安全；没有调用 API，也未模拟 Claude Code 的并发工具调度器。受控 wrapper 在依赖 shell snapshot 的未导出函数/选项时确有语义差异，因此白名单不能泛化为任意 Bash。此阶段的下一项工程工作应是把 hook/原始 eBPF/进程谱系证据整合成一个独立、可审计、只在 controlled profile 启用的 Adapter 关系类型；不能修改默认 inferred/abstain 规则。

## 2026-10-22 controlled-instrumentation Adapter profile（零 API）

- **实现**：新增独立 `controlled_instrumentation_alignment.py`，只在 `plan.json` 显式启用 `controlled_hook_instrumentation` 时运行。结果写到单独的 `controlled-instrumentation/` 子目录，关系类型为 `controlled_instrumentation.tool_to_runtime_process_lineage`；`align_application.py` 的默认三种身份模式没有修改。每条关系保留 Claude 原生 tool-use 行、hook Pre/Post 行、AgentSight SQLite `tool_calls` 行、eBPF carrier 与目标 EXEC 行；报告对原始文件逐个记录 SHA-256，并单独哈希绑定应用事件、plan 和 audit。缺少任一 required evidence 时 abstain。
- **VERIFIED（run45 离线回放）**：4 个 tool starts 中 2 个 Bash 为 2/2 accepted，2 个 Write 因没有 hook/具体 eBPF PID 桥而 2/2 abstain；AgentSight ID 仍 4/4 exact match。通用 `process-and-tool` 维持 abstain 4/4，`shared-tool-id` 和 `session-and-tool` 保持 accepted 4/4。
- **VERIFIED（run46 离线回放）**：同样为 Bash 2/2 accepted、Write 2/2 abstain；通用 `process-and-tool` 仍 abstain 4/4，`session-and-tool` 仍 accepted 4/4。分母按工具类型明示，避免把“两个 Bash 的桥接成功”误写成“四个工具都直接关联进程”。
- **VERIFIED（负条件/规则测试）**：合成 controlled profile fixture 覆盖 exact hook+AgentSight+eBPF carrier/子进程谱系时 accepted；删掉 ID carrier 时，即使语义 `tool_calls` 有同一 ID 仍 abstain；plan 未显式启用时拒绝运行。所有输出均 `responsibility_claim=false`、`ground_truth_used=false`。
- **修复（并发日志完整性）**：回归测试重现 Windows 上 16 个 hook 子进程并发追加 JSONL 时偶发仅 15 行。hook 写入现使用跨进程文件锁后追加一整行并 `fsync`；锁文件放在临时目录而不是实验原始日志目录。全量 `trace_adapter` 测试为 129/129 通过。
- **VERIFIED（唯一性负测）**：若 AgentSight `tool_calls` 内同一 ID 出现两行，不再视为“存在即足够”；profile 要求恰好一条系统语义记录，否则 abstain。新增重复 ID fixture 覆盖该规则。

**结论边界**：这是显式改写工具命令并将 Claude ID 注入 argv 的受控 profile，不是 AgentSight 被动观测能力；也不代表 Write/Read/任意 shell 操作均能绑定到进程。当前 run45/run46 只证明两个故障场景各一个真实 run 的 Bash 子集。通用生产对齐器仍保持既有 abstain/inferred 语义。最终离线回放目录分别位于 run45/run46 的 `alignment-inputs-controlled-profile-v2-final-20261022`；每份都保留按工具分层计数及应用事件、plan、audit 和原始数据哈希。下一 gate 转为受控 profile 的评估：在现有未插桩真实 run 上复核负条件，在至少多个 seed 的白名单工具场景中报告覆盖率与错误关联率，并使用独立/盲化标签；当前两个故障场景各 n=1，暂不足以声称泛化。该 gate 可先用已有原始日志和零 API 本地探针完成。
