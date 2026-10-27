# 跨层关联实现与AgentSight修改记录

核对日期：2026-10-27。只读检查本仓Git历史、当前源码及归档实验报告；未修改源码、未重建或执行真实采集、未提交或推送。使用本地研究质量门；Git工作区存在未跟踪研究文档，未拉取远程以免改变审计基线。

## 结论

VERIFIED：当前讨论的session-and-tool关联，主要实现于my_paper_coding/trace_adapter/align_application.py，运行在AgentSight之外。AgentSight负责产出系统记录，适配器连接应用原生身份与系统记录。不能表述成“修改eBPF程序以识别session_id/tool_call_id”。

在666c7f3父版本的AgentSight源码中，已存在session_id_from_body、tool_call_id提取、related_pid赋值以及工具session_id=None。因此这些基础能力至少早于本轮加固提交，不应算作本轮新增。该结论是本仓历史核对，不是对上游所有版本逐提交溯源。

## 1. 两路数据如何形成

### 应用侧：新增可控运行和原生流适配

capture_real_application.py::capture_agent创建UUID作为session，通过--session-id传给Claude；同时开启stream-json/verbose，保留原始流及每行接收时间，保存运行器指定agent_id、本地PID、namespace与启动时间范围。agent_b来自运行器角色，不是BPF识别。

parse_claude_native.py读取system/init、assistant/tool_use、user/tool_result及terminal result；核对原生session与启动登记一致，以真实tool_use.id和tool_result.tool_use_id闭合调用。一个工具生命周期定义一个adapter Step，step_id=native-tool:<tool_call_id>。记录原始行引用。流式片段不作为多次独立调用，接收时间也不冒充工具实际开始时间。

### AgentSight侧：既有通信解析与视图投影

受支持SSL边界探针→HTTP/SSE解析→CanonicalEvent→view/projection.rs→SQLite。字段不是内核直接理解业务后生成：

- session_id_from_body从请求/响应正文或metadata提取session；也支持metadata.user_id中的编码形式。
- 工具解析从SSE content_block中读取type=tool_use、id、name和input；写ToolCallRow.tool_call_id。
- related_pid来自携带该通信的事件PID，表示Agent/通信进程，不保证是Bash子进程PID。
- 当前相关分支为工具行写session_id=None，所以要由外部关联补会话归属。

## 2. 关联算法

1. 校验manifest、应用文件与原始系统来源哈希、run/host/boot作用域；只消费observed原始观测，不把validator/derived当输入。
2. 对每条tool.start，按session_id在llm_calls记录找会话对应的PID集合；集合必须唯一。
3. 独立按tool_call_id在系统工具记录查找；必须唯一命中。
4. 该工具related_pid必须等于会话PID；接受后保存双方来源引用。
5. 缺记录abstain，重复候选/进程冲突uncertain；多个应用身份指向同一系统工具记录也降为uncertain。

真实库存实验：Agent B session=0f849550-7f03-4805-9d64-edc030b05a24，Bash调用call_00_NGarV3zIFU9lSCjffruH0511；llm_calls.pid和tool_calls.related_pid同为405，工具行session_id为空。该匹配不依赖严格时钟或应用PID直接换算，结果明确标注这两项not_evaluated_in_shared_id_mode。只产生观察关联，不生成责任。

## 3. AgentSight内部可确认的修改

### 666c7f3（提交日期2026-10-12）

提交题目：feat: harden pre-attribution observation pipeline。49个trace_adapter文件在此批量进入历史；不能把提交日期当作每个文件首次开发日期，阶段报告记录了10月10日的实验。

AgentSight本体8文件变更：

- agentsight-capture/src/time.rs：原先缓存整秒boot epoch并换算毫秒，改为realtime/monotonic配对测量纳秒锚点，保留小数部分；多次采样并记录采样不确定度、分辨率下界及失败回退。
- analyzers/timestamp_normalizer.rs：保留_agentsight_clock，包含raw_boot_ns、boot_epoch_ns、epoch_ms、anchor_uncertainty_ns和转换公式。
- analyzers/protocol_events.rs：SSE/HTTP重新构造事件时新增preserve_clock_evidence，避免已有时钟证据丢失。
- model.rs、view/projection.rs：工具行增加三项observer时钟字段，并从事件中读取。
- sinks/sqlite.rs：迁移旧tool_calls表并写入/读回observer_raw_boot_ns、observer_boot_epoch_ns、observer_clock_uncertainty_ns，兼容旧库缺列。
- sources/agent_native.rs、collector/src/cli_db.rs：补充新增工具字段的初始化或传递。

用途：让严格进程/时间关联与复查有依据。不是session/tool双键匹配成立的必要条件。归档报告显示纳秒换算和SSE透传已在单真实会话验证；非零下界及完整新版联合条件不能追溯升级历史数据。非零下界不是总误差已知或仅1ns。

### e5170d4（提交日期2026-10-14）

提交题目：feat: add auditable pre-attribution evidence pipeline。对应进展/实验多记录为10月13日，日期口径分别保留。

AgentSight本体明确修改：

- bpf/process.h：新增namespace_pid。
- bpf/process.bpf.c：新增目标namespace设备号/inode参数，调用bpf_get_ns_current_pid_tgid，在EXEC/EXIT事件记录namespace TGID。
- bpf/process.c：通过/proc/self/ns/pid读取采集器namespace身份，传给BPF；输出namespace_pid；跟踪/过滤逻辑使用可见PID及namespace父进程信息。
- bpf/tests/test_process_runtime.py：增加namespace字段验证；更新vendor process二进制。

用途：直接关联不同PID namespace视图，避免仅凭进程名和时间猜测。experiment_20261013_13证明标记进程1791→34且用户态PID=34；尚未证明新真实多Agent联合会话稳定覆盖。

同提交还新增外部可查询证据包、模型上下文及验收模块；它们不都属于AgentSight本体修改。

## 4. 两种关联不要混淆

| 内容 | 当前来源与证据 |
|---|---|
| 应用工具→系统工具 | 适配器共享session/tool ID+系统PID核对；真实多Agent样例已运行 |
| 本地PID→观测PID | 先前间接证据，后新增namespace内核直接机制；标记进程实测 |
| 应用时钟→系统时钟 | 纳秒锚点与透传/存储修复；历史事件严格界仍有不足 |
| 观察身份→责任原因 | 不由这些改动自动产生，仍需归因与验证 |

## 5. 可复核来源

- git show 666c7f3 -- lab/agentsight/source/thesis_adapter
- git show e5170d4 -- lab/agentsight/source/thesis_adapter
- git show 666c7f3^:lab/agentsight/source/thesis_adapter/ext/analysis/src/view/projection.rs
- my_paper_coding/trace_adapter/{capture_real_application.py,parse_claude_native.py,align_application.py}
- lab/agentsight/source/thesis_adapter/ext/analysis/src/view/projection.rs：session_id_from_body、metadata_user_session_id与工具投影分支。
- lab/experiment/experiment_20261012_14/、experiment_20261013_13/；my_paper/进展/v0.15—v0.20。

下一研究门：归因只能消费各自通过质量门的关系；不因内部采集机制修复就将历史推断或缺失记录升级为直接证据。
