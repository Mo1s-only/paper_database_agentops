# AgentOps 论文问题定位与方向研讨

日期：2026-10-21  
目标：判断“AgentSight/eBPF 系统证据 + Agent 语义证据”能否形成可发表的 AgentOps 研究问题，并明确差异化边界。

## 当前建议

建议采用“方向 01 + 方向 05”的收敛组合：保留跨层责任边归因作为目标，但把论文主贡献先定位为一项**实证驱动的方法研究**：测量 AgentSight/eBPF 系统副作用证据在不同多 Agent 故障类型、不同采集缺失/对齐强度下，相比语义层日志能否带来责任 Agent/Step/Edge 定位增益，并用受控重放/干预验证关键边。

不要把论文定位为“首次融合 Agent 语义和 eBPF”。AgentSight 已经把语义—系统跨层观察与关联作为核心；也不宜声称“首次为多 Agent 故障建立因果图并反事实验证”，因为已有多 Agent 归因工作研究依赖图和反事实式细化。论文差异要落在**系统实测副作用对多 Agent 责任边归因的条件性增益、可审计的跨源关联质量，以及可执行干预验证**上。

## 当前候选研究问题

> 在多智能体任务失败时，在哪些故障类型和观测缺失条件下，加入 eBPF 观测到的进程/文件/网络副作用，相较于仅使用 Agent 语义轨迹，能否提高责任步骤或责任边定位；这些候选责任边能否通过受控重放或干预验证？

| Gate | 当前表述 |
|---|---|
| Object | 有消息、工具调用、Agent 进程及文件/网络副作用的多 Agent 执行；重点是工具/环境故障及其跨 Agent 传播 |
| Intervention | 来源保真的双源 Adapter + 直接/推断/不可判定关系状态 + 责任边候选排序 + 局部重放/干预 |
| Measurement | Edge/Step Hit@k、MRR、Macro-F1；关系 provenance 完整率与 abstention；有效修复翻转率、无关控制误翻转率；开销/成本 |
| Baseline | 最终输出；语义日志归因；AgentSight 原生关联/分析；时间/PID 规则；加入系统边但不做反事实；加入反事实的方法 |
| Boundary | 观察到的相关关系不等于因果；AgentSight 系统与单一 Agent 框架不能支撑普遍泛化；不声称访问隐藏思维链或已实现自治修复 |

## 可证伪假设草案

- H1：在静默工具错误、文件/网络副作用错误等环境相关故障上，语义+系统副作用组相较语义-only 组能改善 Edge/Step 定位；若无稳定差异，否定核心增益主张。
- H2：在纯语义/路由判断故障上，eBPF 的增益应小于环境副作用故障；若没有故障类型差异，需重审系统信号的理论作用。
- H3：跨源关联证据变弱或缺失时，准确性/覆盖率会下降，fail-closed 的 abstain 能控制错误强连边；需分开报告 coverage 与 precision。
- H4：受控修复预测责任边应比无关边干预更常翻转任务结果；仅靠 LLM 对反事实文本的自我评分不算系统因果验证。

## Claim–Evidence–Gap

| Claim | Evidence | 状态 | 缺口 |
|---|---|---|---|
| AgentSight 论文已经涵盖语义意图与内核事件跨层关联 | AgentSight 原论文摘要/贡献，称 boundary tracing、eBPF kernel events、跨进程关联及 secondary LLM analysis | VERIFIED（论文自述范围） | 需精读方法和评估，与本研究具体任务、输出粒度逐项比较 |
| 多 Agent 语义轨迹上的图归因和反事实式步骤定位已有相关工作 | AgentTrace (ICLR 2026 Agents in the Wild Workshop)、DCFA、CausalFlow 预印本 | VERIFIED（来源与论文摘要/正文） | 需逐篇核对其真实干预强度、标签和复现条件，不能仅凭摘要比较 |
| Agent 语义 profiling、Agent 的进程—文件 eBPF provenance 已分别成为相邻竞争方向 | AgentPProf 预印本；Agent-Warden 预印本页面标注 accepted for IEEE TPS 2026 | VERIFIED（论文页面所述） | 需查全文和正式出版信息，明确任务与本研究的重叠/区别 |
| 当前本地实验已存在可用的分层证据与原型 | 既有 P0 配对、真实 inventory-silent-tool pilot、Adapter 测试和报告；run 9 原生日志 + AgentSight SQLite | VERIFIED（限定于各自记录范围） | 需从冻结原始数据独立重算，区分旧成功运行与最新响应体缺失运行 |
| eBPF 信号能稳定提升多 Agent 责任边定位 | 目前没有充分的对照统计 | UNVERIFIED | 设计语义-only / 系统增强 / 反事实组，采集可复现真值和重复样本 |
| 跨层责任边具有真实因果意义 | 单条受控运行的离线判据回放不能证明总体系统因果效应 | UNVERIFIED | 真实可重放的修复与无关干预控制、随机性重复及不确定区间 |

## 方向候选比较（规划判断，非实验结果）

| 候选 | 发表潜力 | 当前可行性 | 主要风险 | 建议 |
|---|---:|---:|---|---|
| A. 只做“语义+eBPF融合工具” | 低 | 高 | 与 AgentSight 既有贡献过度重叠，容易被评为工程集成 | 不作为论文主定位 |
| B. 新的跨层因果归因算法 | 中高 | 中低 | 与多 Agent 图归因/反事实方法竞争；需要强算法差异、稳定真值与实际干预 | 可保留为方向 01 的长线目标，不先承诺算法 novelty |
| C. 系统证据增量价值的控制性实证 + 可审计归因流程 | 中高 | 中高 | 实验设计需严谨，样本与对照不能只来自单个成功案例 | 当前首选；方向 01 + 05 组合 |
| D. AgentOps 信号与指标校准 | 中 | 高 | 若只有描述统计会显得弱 | 当跨层匹配/干预长期不可靠时的保底路线 |

上述排序是研究规划推断，不是发表概率或投稿保证。实际 venue 应在初步对照结果后再选。

## 当前证据与实验约束

- 本地框架已有方向 01 的 Agent/Step/Edge、反事实和消融设计，也把方向 05 列为风险可控的 fallback。
- 既有受控 harness 和单条真实 `inventory-silent-tool` pilot 可以证明原型闭环可运行，不能证明总体归因效果。
- 最近 run 9 记录到 Claude 原生 Bash/Write 事件和 AgentSight 系统事件；同次 AgentSight 数据中 LLM 行响应体为 `null`，`tool_calls`/`token_usage` 为 0。该运行不能证明完整跨层语义 join，也不是多 Agent 归因实验。
- 真实 API 费用账已接近既定 hard stop；本方向的下一轮应先做零 API 适配/证据审计和离线可复验实验。任何后续付费调用必须重新核账、预算和授权。

## 检索记录

- 检索日期：2026-10-21。
- 检索问题：AgentSight 的论文贡献边界；多 Agent failure attribution/counterfactual work；Agent profiling 和 eBPF provenance 的近期重叠方向。
- 纳入来源：优先原论文/论文页面（arXiv、OpenReview、ACL Anthology），并结合本地 `方向框架/`、`my_paper_coding/` 与 `lab/experiment/`。
- 核心来源：
  - AgentSight, *System-Level Observability for AI Agents Using eBPF*, https://arxiv.org/abs/2508.02736
  - AgentTrace, *Causal Graph Tracing for Root Cause Analysis in Deployed Multi-Agent Systems*, ICLR 2026 Workshop on Agents in the Wild, https://openreview.net/pdf?id=22qiB2JpzZ
  - DCFA, *Dual-view Causal-inspired Attribution for Failure Reasoning in LLM-based Multi-agent Systems*, https://arxiv.org/abs/2609.04749
  - CausalFlow, *Causal Attribution and Counterfactual Repair for LLM Agent Failures*, https://arxiv.org/abs/2605.25338
  - TELLER, *Non-intrusive Cross-Layer Root-Cause Analysis for LLM Inference*, https://arxiv.org/abs/2608.01975
  - AgentPProf, *Semantic Profiler for Long Horizon AI Agents*, https://arxiv.org/abs/2609.20301
  - Agent-Warden, *eBPF-Based Kernel-Native Process-File Provenance Tracking for LLM Agents*, https://arxiv.org/abs/2609.38245
- 后续需查全文/版本：以上近期工作与本地 PDF/文献索引还未全部完成逐节核对；本记录只支持初步定位，不替代正式 related-work 审计。

## 研讨问答与开放项

### Q1（待用户确认）

我当前建议优先做一篇**证据增量价值的控制性实证论文**，以方向 01 的跨层责任边方法为系统载体、方向 05 的严谨指标/消融为核心证据；先追求范围清晰、可复现、可投稿，不预设 CCF A 类目标。你当前最优先的是这个“较稳妥发表路径”，还是宁可承担更高实验/算法风险去冲更强的算法型论文？

推荐选项：先走较稳妥发表路径；若第一轮对照显示强而稳定的边级增益，再升级为算法型主张。

Open flags:

- 具体毕业/投稿 deadline：AUTHOR_INPUT_NEEDED。
- 导师或学院是否指定 venue/分级：AUTHOR_INPUT_NEEDED。
- 可公开的 trace、原生日志与运行环境范围：AUTHOR_INPUT_NEEDED。
- 新适配器/关系审计是否能从冻结原始运行中复算：待零 API 验证。

## 新一轮创新性拓展｜用户指出融合方向仍显得不够创新

用户反馈：仅“语义层 + eBPF 系统层作为数据链，再做归因”看起来仍不足以构成创新。该反馈被记录为当前方向的关键风险，而非要求用户接受原定位。

### 更新后的竞争边界

- AgentSight 已提出语义意图与内核行为跨进程关联；所以“跨层融合”不是可靠的新颖性主张。
- Agent-Warden 已做 LLM Agent 的 eBPF 进程/文件 provenance 与内核侧因果边；所以“eBPF 系统因果链”本身也有直接竞争。
- AgentPProf 已研究长程 Agent 语义操作栈与资源/问题 profiling；所以泛化的 Agent 语义 profiling 也拥挤。
- TraceElephant（ACL 2026）已建立多 Agent 全执行 trace 归因基准，并比较部分/完整可观测性；TelemetrySuffBench 已系统研究 telemetry mask、故障源定位与证据不足时的 abstention。因此“trace 越完整越好”或“缺失数据下 abstain”单独不足以形成新主张。
- DCFA/CausalFlow 已研究执行依赖图、决定性步骤与反事实式归因；所以“因果图 + 反事实”也不能只作为组合式 claim。

来源：AgentSight https://arxiv.org/abs/2508.02736；Agent-Warden https://arxiv.org/abs/2609.38245；AgentPProf https://arxiv.org/abs/2609.20301；TraceElephant https://aclanthology.org/2026.acl-long.912/；TelemetrySuffBench https://arxiv.org/abs/2608.07899；DCFA https://arxiv.org/abs/2609.04749；CausalFlow https://arxiv.org/abs/2605.25338。该竞争图仍是初筛，需全文逐方法比较后才能形成正式 related work gap。

### 可扩展问题候选（规划判断，不代表已验证新颖性）

| 方向 | 真正研究对象 | 初步新颖性 | 可行性/风险 | 判断 |
|---|---|---:|---|---|
| A. 语义—运行时副作用偏离及其传播归因 | Agent 声明/请求的工具动作，与 eBPF 观察到的实际进程、文件、网络效果不一致；定位最早偏离边并追踪下游 Agent 如何消费错误状态 | 中高（待系统查重） | 中；需可观测的 mismatch、独立任务状态和真实干预 | **首选扩展**：从“融合数据”改成“检测、解释和验证声明—效果偏离” |
| B. 不确定性触发的按需观测 | 当语义—系统关系不清或副作用冲突时，主动追加更细粒度证据；其余时候低开销采集 | 中（已有自适应采集邻域） | 中低；需要在线策略、Pareto 与观测者效应评估 | 可作为后续系统贡献，不先做主线 |
| C. eBPF 增强的多 Agent 故障归因基准 | 成对发布 Agent 语义、OS 副作用、任务状态 oracle、故障注入和可重放干预标签 | 中高（真实跨层标注可能有价值） | 低；隐私许可、样本量、环境重放和标注成本大 | 有资源后再做数据集/benchmark 论文 |
| D. 传播前选择性隔离或阻止副作用 | 在错误状态被下游 Agent 消费前，依证据置信度延迟、验证、隔离或拒绝不可逆动作 | 高潜力但不确定 | 低；需在线预测、误拦截代价、安全沙箱和净效用 | 远期方向；目前不宜扩成自治保障论文 |

### 当前首选定位（需查重后再定）

把“多源数据链”降为实现基础，把待验证的核心问题提升为：

> 在多 Agent 工具执行中，语义层声明的动作与内核观察到的实际副作用发生偏离时，能否定位最早的语义—运行时偏离，并证明该偏离是否沿 Agent 间消息/状态依赖传播为任务失败？

建议把 `semantic claim → tool invocation → observed process/file/network effect → task-state transition → downstream agent consumption` 作为候选分析链。前四段不是天然因果；只有对候选偏离做可复现局部干预（修复/屏蔽该副作用，并设置无关边控制）后，才将关系报告为经干预支持的责任边。

本定位与纯语义多 Agent 归因的差别，在于研究“系统实际效果与应用层声明/结果之间的差异”及其在多 Agent 中的传递；与通用 AgentSight correlation 的差别假设在于**面向偏离/矛盾检测、责任边定位、干预验证的任务定义和实验协议**。这个差异只是 `INFERRED / novelty hypothesis`，不是已完成的系统综述结论。

### 该方向的可证伪 Go/No-Go

以零 API 可重放/确定性 harness 先构造或重放三类场景：工具声称成功但副作用缺失；产生请求之外的文件/进程/网络副作用；副作用发生正确但下游 Agent 错误消费/传播。随后用少量真实运行验证外部效度，不把真实 API 作为批量标签生成器。

- **Go**：确实存在语义事件与系统效果可独立观测的偏离；运行时效果证据能定位到语义-only / 现有 AgentSight 分析漏掉或混淆的上游责任边；修复该边可重复改变独立任务 oracle，无关控制不改变结果；收益不是来自把更多原文塞给同一个 LLM。
- **No-Go**：现有 AgentSight correlation 已能同等识别和验证该类偏离；或现有运行不能稳定产生独立的实际效果真值；或只有时间/PID 共现、没有可执行干预。此时不应包装成新因果方法，优先收缩到方向 05 的可观测信号效用/失效模式实证，或做真实跨层数据集（如果许可/规模可行）。

当前 run 9 只证明语义工具日志和系统事件在同次运行分别存在，且 AgentSight 部分 LLM 结构化字段缺失；它尚未展示经过独立确认的“声明—效果偏离”，也没有多 Agent 传播或因果干预。因此该候选问题目前仍为 `UNVERIFIED`。

### Q2（待用户确认）

我建议下一阶段把主问题从“如何把两层数据连接起来”改为“如何检测并验证 Agent 语义声明与 eBPF 实际副作用之间的偏离及其跨 Agent 传播”，把 Adapter 作为支撑方法。你是否愿意把这个“语义—运行时偏离”作为论文核心；还是更想优先研究“按需采集/选择性干预”？

推荐选项：先研究语义—运行时偏离及可验证传播归因；按需观测和在线阻断留作扩展。
