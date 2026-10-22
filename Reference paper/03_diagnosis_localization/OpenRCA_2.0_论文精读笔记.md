# OpenRCA 2.0 论文精读笔记

> 精读日期：2026-10-19  
> 阅读状态：全文精读（正文、数据说明、PAVE 细节、Agent 协议和评价指标）  
> 证据标签：`VERIFIED` 表示可由论文或本地实验材料直接支持；`INFERRED` 表示基于证据的研究判断；`UNVERIFIED` 表示尚未有足够实验支持；`AUTHOR_INPUT_NEEDED` 表示需要作者本人做方向选择。

## 0. 论文信息

- 标题：**OpenRCA 2.0: From Outcome Labels to Causal Process Supervision**
- 作者：Aoyang Fang、Yifan Yang、Jin'ao Shang、Qisheng Lu、Junjielung Xu、Rui Wang、Songhan Zhang、Yuzhong Zhang、Boxi Yu、Pinjia He
- 单位：The Chinese University of Hong Kong, Shenzhen 等
- 文献类型：预印本；PDF 首页未给出正式会议或期刊
- arXiv：`arXiv:2606.27154v2 [cs.AI]`，PDF 标注日期为 2026-06-30
- 本地论文：[OpenRCA_2.0_Causal_Process_Supervision_2026.pdf](OpenRCA_2.0_Causal_Process_Supervision_2026.pdf)
- 本地数据说明：[R30 — OpenRCA 2.0](../datasets/R30_OpenRCA_2_0/README.md)
- 阅读目的：过程级因果真值、传播边标注、RCA Agent 评价，以及它与“多 Agent 跨层因果边归因与可验证诊断”的关系
- Artifact 状态：论文称匿名预览和完整包随投稿提供，并计划录用后公开数据及 PAVE pipeline；本仓库截至 2026-10-16 尚未找到可独立核验的公开 artifact，故公开可复现性状态为 `UNVERIFIED`。

## 1. One-sentence contribution

OpenRCA 2.0 提出 PAVE：利用故障注入时“标注者知道干预、诊断 Agent 不知道干预”的信息不对称，从已知根故障出发，通过结构规则、基线偏离和时间顺序的联合筛选，自动重建服务故障的逐步传播图，并据此把 RCA 评价从“是否猜中根因”推进到“是否给出可验证的传播过程”。

## 2. 这篇论文真正解决了什么

现有微服务 RCA benchmark 通常只保留最终标签：哪个服务被注入了什么故障。它们可以评价 Agent 是否命中根因，却不能判断 Agent 给出的推理链是否真实经过系统中的传播路径。

论文把这一缺口称为 **ungrounded diagnosis（未扎根/无依据诊断）**：

> Agent 找到了正确的根因服务，但没有画出从该服务到已观察症状的有效传播路径，甚至跳过中间服务或凭空增加边。

这不是措辞问题，而是评价对象发生了变化：

```text
旧评价：root cause label 是否正确
新评价：root cause + affected nodes + directed edges + path to alarm 是否共同正确
```

论文最有价值的结论不是“某个模型更强”，而是证明了 outcome-only 指标会系统性掩盖路径推理错误。

## 3. Problem setting

### 3.1 系统与观测

- 系统：Kubernetes 上的微服务应用。
- 系统结构：服务、Pod、容器和主机组成的有向依赖图 `G=(V,E)`。
- 水平传播：沿 RPC 调用链传播，例如下游 Seat 延迟导致 Travel、Order、Gateway 连续超时。
- 垂直传播：基础设施故障跨层影响服务，例如共享节点或 Pod 的资源争用影响多个服务。
- Agent 可见观测：分布式 traces、时序 metrics、结构化 logs。
- Agent 不可见信息：故障注入本身及注入位置。

### 3.2 分析单位

论文同时涉及四类粒度：

1. 根因标签：`(service, fault_kind)`；
2. 节点：service、pod、span 及其异常状态和起始时间；
3. 边：故障从 source 传播到 target 的有向因果弧；
4. 路径：从根因节点到 alarm node 的有向路径。

### 3.3 输入与输出

PAVE 的输入是：

```text
依赖图 G
+ 注入窗口内的多模态观测 O(t)
+ 已记录的干预 do(v_root)
```

输出是经过筛选的传播路径集合 `Π*`，所有路径的边集构成过程级真值图 `G*`。

## 4. Method core：PAVE 如何构造过程真值

PAVE 全称 **Path Annotation via Verified Effects**。它利用已知干预把“从症状反推原因”的不适定问题，转换为“从已知原因向前检查哪些影响真实发生”的验证问题。

### 4.1 核心信息不对称

诊断 Agent 只能看到 `O_obs`；PAVE 还知道 `do(v_root)`。因此：

```text
Agent：O_obs → 反向推断 root/path
PAVE：do(v_root) + O_obs → 前向验证 path
```

这项设计的关键不是让标注算法比 Agent 更聪明，而是让标注端合法使用 Agent 不可见的实验控制信息。

### 4.2 Phase 1：Structural Pruning

第一阶段回答：“这条边在系统结构和故障机制上是否可能发生？”

1. 使用节点类型感知映射 `Ψ`，把高维 telemetry 映射为离散状态，例如：
   - 服务/span：`HighLatency`、`HighErrorRate`、`Timeout`、`Missing`；
   - Pod/container：`CPU_Throttled`、`MemoryPressure`、`Restart`。
2. 在 time-expanded heterogeneous graph 中，把节点表示为 `(component, state, time)`。
3. 使用传播规则集 `R` 限制合法状态转移。
4. 从注入位置做 constrained DFS，将环形依赖展开为有限的无环候选链。
5. 得到候选路径集合 `Π_cand`。

规则集覆盖四类机制：

- container/pod → service/span 的垂直资源传播；
- service → span 的首跳状态继承；
- span → span 的 RPC 延迟、错误、缺失、重试等水平传播；
- span → pod → span 的跨通道传播。

论文默认最大路径长度为 5，单节点最多重访 2 次；规则默认置信度为 0.8（Appendix D.5-D.6）。

### 4.3 Phase 2：Causal Verification

第二阶段回答：“结构上可能的链，是否真的在这次注入中承载了异常信号？”

对每次注入，论文从故障前正常窗口构造 reference baseline。候选路径只有同时满足以下三类条件才进入 `Π*`：

1. **统计条件**：路径上每个节点都显著偏离其故障前基线；
2. **结构条件**：每条连续边都符合传播规则 `R`；
3. **时间条件**：下游异常的起始时间不早于上游原因。

节点异常检测按指标分布使用三类检测器：

- 近似高斯指标：Z-score；
- 重尾指标：经验分位数；
- 请求延迟：依据基线均值和变异系数调节阈值的自适应检测器。

单节点检测有意偏向低漏检；误报由“统计 × 结构 × 时间”的联合门过滤。论文在 Appendix D.8 给出一个近似独立假设下的误路径概率上界，但明确承认三类条件并非完全独立。

### 4.4 实例进入数据集的额外条件

一个注入运行只有同时满足以下要求才保留：

- 对下游产生跨越 SLO surface 的可观测异常；
- 至少存在一条规则允许、时间一致的根因到症状路径；
- 注入前基线没有明显漂移。

静默注入、无有效传播链、前置基线异常等实例会被过滤。

### 4.5 对“causal”的准确理解

`VERIFIED`：根节点来自真实受控干预，传播方向由已知注入锚定；候选边还必须满足机制、统计和时间三重证据。

`INFERRED`：PAVE 构造的是“由已知干预锚定、并由多重观测条件支持的传播图”，比仅凭共现或时间先后生成的图更强。

`INFERRED`：它仍不是对每一条传播边分别执行删除、替换或重放后的 edge-level counterfactual proof。边级因果性主要来自根干预、结构机制和观测一致性的组合，因此更合适的表述是 **intervention-anchored verified propagation**，不宜扩写成“每条边均由独立干预证明”。

## 5. OpenRCA 2.0 数据集

### 5.1 数据规模

| 系统 | 服务数 | 技术栈/通信 | 可评价实例 | chaos primary kinds | 平均最长路径 | 平均因果边数 |
|---|---:|---|---:|---:|---:|---:|
| TrainTicket | 44 | Java / REST | 320 | 25 | 3.0 | 10.1 |
| OpenTelemetry Demo | 15 | polyglot / gRPC + Kafka | 38 | 9 | 2.5 | 3.0 |
| Hotel Reservation | 9 | Go / gRPC | 142 | 5 | 2.1 | 2.7 |
| 合计/总体 | - | 三种架构 | **500** | **27** | **2.7** | **7.5** |

数据来自 **8,137** 次故障注入运行，经静默注入过滤、PAVE 验证和分层抽样后得到 500 个实例。分层维度为 `(system, chaos family, root service)`，并设置每层上限。

### 5.2 每个实例包含什么

1. 故障前与故障后的多模态 telemetry：traces、metrics、logs，使用 parquet；
2. 结构化根因标签：系统、注入组件、故障类型；
3. 过程图 `causal_graph.json`：
   - `nodes`：组件、异常状态、onset timestamp；
   - `edges`：`source → target` 的传播边；
   - `root_causes`：传播起点；
   - `alarm_nodes`：注入窗口内观察到异常的下游终点。

### 5.3 故障类型

论文使用 Chaos Mesh 覆盖应用、资源、网络、Pod、JVM、DNS 和时间偏移等故障。评价时不直接要求 Agent 猜中底层 Chaos API 名称，而把观测上不可区分的注入机制合并为 **observable fault-kind vocabulary**，例如：

- `pod_failure`、`pod_unavailable`；
- `network_delay`、`network_loss`、`network_partition`；
- `http_aborted`、`http_slow`、`http_payload_modified`；
- `cpu_stress`、`mem_stress`、JVM stress/exception/latency；
- `dns_resolution_failed`、`clock_skew`。

这是一个重要的评价纪律：真值标签粒度不能超过观测可辨识粒度。

### 5.4 数据集边界

- 无固定 train/development/test 划分；
- 目标是覆盖不同系统和传播结构，不代表生产事故分布；
- 排除循环服务图、传播深度不超过 1 的简单实例，以及 frontend/load-generator 根因；
- 只保留有可观察传播签名的故障，因此不能评价“完全无 telemetry 信号”的故障；
- 500 个实例中 TrainTicket 占 320 个，pooled 指标受系统混合比例影响。

## 6. RCA Agent 实验设计

### 6.1 Agent 架构

所有模型使用相同的 tool-augmented ReAct 风格流程：

```text
DecisionNode（分析/调用工具）
    ↕
ExecutionNode（异步执行工具并返回观察）
    ↓
SynthesisNode（压缩为结构化 CausalGraph JSON）
```

统一工具包括：

- 列举 parquet 文件；
- 获取 schema；
- 用 DuckDB SQL 查询 telemetry；
- `think_tool` 记录调查摘要和下一步计划。

每例建议约 50 个工具调用，硬上限为 100。Agent 不会获得系统依赖图，必须从 trace 数据中推断服务关系，以避免 topology leakage。

### 6.2 输出契约

Agent 输出两部分：

- `root_causes[]`：`service + fault_kind + evidence[]`；
- `propagation[]`：`from + to + evidence[]`。

每个根因和每条边都必须携带至少一个可重新执行的 DuckDB SQL 查询及不超过 20 个词的 claim。

需要注意：主表中的 `SQLExec` 只检查 SQL 是否成功执行且返回至少一行，不检查返回行是否真正支持自然语言 claim。论文在设计中提到 `evidence_support_rate`，但核心结果表没有把语义支持率作为主结果报告。

### 6.3 模型

主实验比较 11 个模型：Claude Opus 4.7、Gemini 3.1 Pro、Claude Sonnet 4.6、MiMo 2.5 Pro、GLM 5.1、Kimi K2.6、DeepSeek V4 Pro、Qwen 3.6-Max、Hy 3.0 Preview、Seed 2.0 Pro 和 MiniMax M2.7。

Appendix H.3 另给出 GPT-5.4（`n=114`）和 GPT-5.5（`n=32`）的部分结果；论文明确说明二者因 API 预算限制未跑完全量，不能直接与主表比较。

## 7. 评价指标

### 7.1 Outcome-level

- **Exact Match (EM)**：预测的 `(service, fault_kind)` 集合与真值完全一致；
- **Precision / Recall / F1**：在 `(service, fault_kind)` 对上逐例计算并取平均；
- **AnySvc**：忽略 fault kind，只要命中至少一个正确根因服务即通过。

### 7.2 Process-level

- **Path Reachability (PR)**：至少命中一个正确根因服务，并在预测图中存在从该服务到某个真值 alarm node 的有效有向路径；
- **Node F1**：预测服务节点集合与真值节点集合的 F1；
- **Edge F1**：预测服务级有向边集合与真值边集合的 F1；
- **SQLExec**：证据 SQL 可执行并返回非空结果的比例。

PR 是最宽松的过程指标：只要求一个正确锚点和一条有效路径，不要求恢复完整传播图。因此 PR 通过不代表边集或路径覆盖完整，严格判断仍要看 Edge F1、Node F1 和 graph coverage。

## 8. 核心实验结果

### 8.1 跨 11 个模型的平均结果

| 指标 | 平均结果 | 含义 |
|---|---:|---|
| Exact Match | **20.7%** | 完整根因集合很难恢复 |
| Pair-level F1 | **34.1%** | 服务与故障类型联合判断较弱 |
| AnySvc | **76.0%** | 至少命中一个正确服务相对容易 |
| Path Reachability | **61.5%** | 正确服务未必能接入正确传播路径 |
| Node F1 | **62.2%** | 受影响服务集合识别尚可 |
| Edge F1 | **43.4%** | 有向传播关系明显更难 |

AnySvc 与 PR 相差 **14.5 个百分点**。换句话说，在所有实例中有 14.5% 出现“服务命中但路径不成立”；相对于 AnySvc 命中的实例，这一比例约为 19.1%，即论文所说“约五分之一的正确服务识别没有得到传播路径支撑”。

### 8.2 最关键的三项发现

1. **Outcome 分数掩盖过程失败。** 只看服务是否命中，会把猜中、模式匹配和真正的传播推理混在一起。
2. **Edge F1 对所有模型都低于 Node F1。** 平均差距为 18.8 个百分点，说明“参与了哪些服务”接近集合分类，而“它们如何有向传播”需要更难的结构推理。
3. **没有单一模型在所有指标上占优。** 不同模型的 outcome、path、edge 和 SQL 能力排名不同，选择模型应与下游验证成本和风险相匹配。

### 8.3 系统复杂度影响

Hotel Reservation 只有 9 个服务、平均最长路径 2.1，顶尖模型的 AnySvc 接近饱和；TrainTicket 有 44 个服务、平均最长路径 3.0，过程指标明显更低。论文据此提醒：服务数、链深和系统混合比例会显著影响 pooled 分数。

## 9. 论文识别出的三类 Agent 失败模式

### 9.1 过早承诺、探索不足

Agent 发现一个显眼根因后立即停止，遗漏并发故障、细微根因或中间传播服务。混合故障中特别明显。

### 9.2 对“有活动”的偏置

Agent 把“没有 span/log”误当作“没有故障”。例如 Pod 被杀后不再产生 span，Agent 反而把故障归因给仍在输出错误的上游调用方。这里“缺失”本身就是故障信号。

### 9.3 被最响亮信号吸引

Agent 容易选择异常幅度最大的服务，而它可能只是下游放大器。强日志文本甚至会压过与其矛盾的低延迟 trace 证据。

这三类错误都说明：RCA 不能只做异常强度排序，还要检查异常方向、调用依赖、缺失模式和跨模态一致性。

## 10. 标注可靠性

论文从 500 个实例中均匀随机抽取 100 个，由两名具备分布式系统可观测性经验的论文作者独立检查 PAVE 生成的 `G*`：

- case-level agreement：**94/100 = 94%**；
- 6 个分歧全部是 PAVE 漏掉了标注者认为可能成立的弱路径；
- 审计样本中，没有标注者指出 PAVE 已包含的边明显不合理。

论文据此选择“高精度、允许保守欠覆盖”的真值策略。

需要保留的边界：

- 审计者是论文作者，不是独立外部 SRE；
- 判据是整例二元 `AGREE/DISAGREE`，不是每条边的独立一致性系数；
- 审计检查的是 telemetry 下的合理性，不是为每条边重复执行独立干预；
- 随机样本覆盖了全部系统和 fault kind，但不是分层平衡抽样。

## 11. 论文的优点

1. **抓住了评价错位。** 论文没有把“模型猜中根因”当作“模型理解了故障”。
2. **标注端和评价端严格隔离。** PAVE 使用注入信息构造真值，但被评 Agent 看不到注入和拓扑。
3. **同时保留节点、边、路径。** 允许区分定位能力与传播推理能力。
4. **证据可重执行。** 每个预测声明绑定 SQL，至少能检查证据检索是否真的发生。
5. **标签粒度尊重可辨识性。** 无法从 telemetry 区分的 Chaos API 被合并为 observable fault kind。
6. **主动报告系统难度差异。** 不把 pooled 排名误当成跨架构稳定能力。
7. **数据说明完整。** 包括采集、筛选、许可、复现、适用范围和风险边界。

## 12. 局限与威胁

### 12.1 论文明确承认的限制（VERIFIED）

1. PAVE 需要真实受控干预，而不是推断出的根因标签；
2. 依赖图必须足够完整，否则真实传播会在结构裁剪阶段被删除；
3. 故障必须在 trace、metric 或 log 中留下传播签名；
4. 注入前基线必须近似无干预分布；
5. 传播规则词表可能漏掉未知机制；
6. 结果只在受控 testbed 范围内成立，不能直接外推生产系统；
7. 标注阶段依赖完整 telemetry；
8. benchmark 不用于生产就绪认证，也不支持对 serverless、service mesh 或完全事件驱动系统的直接泛化声明。

### 12.2 本笔记的进一步判断（INFERRED）

1. **过程真值仍有选择偏差。** 只有能形成可观测有效路径的运行才进入数据集；完全静默、短链和结构异常案例被排除，故 benchmark 更适合评价“路径恢复”，不等同于真实事故分布。
2. **边级因果强度有限。** 根干预是真实的，但中间边主要由规则、偏离和时间顺序支持；没有逐边干预时，仍可能存在未建模共同原因或替代路径。
3. **Eq. (3) 的误报上界依赖近似独立。** 统计、结构和时间条件共享信息，不能把示例概率当作经验误报率。
4. **主表的证据评价偏机械。** SQL 能执行不等于 SQL 返回内容支持 claim；如果把“可执行”写成“证据正确”会过度解读。
5. **标题中的 process supervision 主要体现为标注和评价。** 论文提出未来可训练 reliability-domain PRM，但本论文没有展示用这些过程标签训练模型后的提升。
6. **模型成本会影响可比性。** GPT 部分模型因预算未跑完，说明大规模 tool-augmented RCA 的比较需要预注册预算、失败处理和覆盖率。

## 13. 与我的方向的关系

当前主方向是一条明确的多 Agent 路线：

> 把消息、LLM 调用、工具、进程、文件、网络和任务结果统一为带类型的跨层证据图，定位“哪个 Agent 的哪个步骤通过哪条责任边导致失败”，再用局部重放或反事实干预验证诊断。

### 13.1 对象与方法对照

| 维度 | OpenRCA 2.0 | 我的方向 | 研究含义 |
|---|---|---|---|
| 目标系统 | 微服务系统 | LLM 多 Agent 协作系统 | 对象不同，不能把服务 RCA 结果直接外推 Agent 责任 |
| 基本实体 | service、pod、container、span | run、agent、step、message、LLM/tool call、system effect | 我的图具有 Agent 角色和任务语义 |
| 主要传播 | RPC 和共享资源 | 消息、数据、控制、工具结果、文件/进程/网络副作用 | 我的边类型更贴近责任传播而非仅故障扩散 |
| 标注锚点 | 已知 chaos intervention | 预冻结故障注入、任务 oracle、决定性步骤/边 | 可以直接借鉴“已知干预只用于真值端” |
| 过程真值 | node、edge、root、alarm、path | responsibility Agent/Step、root node、propagation edge、full path | 我的五类真值协议覆盖更细的责任层级 |
| 验证方式 | 结构 + 统计 + 时间联合门 | 候选搜索 + 删除/替换/重放 + 无关控制 | 我的目标是把观测定位进一步升级为反事实责任验证 |
| 证据 | 每项预测附可重执行 SQL | source pointer、JSON Pointer、SHA-256、原生 ID、重放结果 | 我的现有 provenance 更强调来源不可伪造与跨层身份 |
| 信息消融 | 论文提出 restricted telemetry 为未来工作 | 消息-only、工具/环境、完整跨层证据对照 | 这是与论文最直接、最可发表的差异点之一 |
| 成本问题 | 工具调用上限；部分模型受 API 预算影响 | 观测、重放、模型调用成本与 Pareto 前沿 | 可将成本从运行约束提升为研究变量 |

## 14. 对我这个方向的具体启示

### 14.1 把“正确答案”升级为“正确责任过程”

本课题不能只报告 Agent/Step Top-1。应定义多 Agent 版本的 ungrounded diagnosis：

> 责任 Agent 或步骤命中，但预测的消息、数据、控制或工具传播边无法连接到最终任务失败，或反事实修复不能翻转结果。

建议增加：

- `Attribution Reachability`：正确责任 Agent/Step 能否沿预测边到达失败 outcome；
- `Ungrounded Attribution Rate`：Agent/Step 命中但 reachability 失败的比例；
- `Validated Edge Rate`：预测边中通过 L2/L3 干预的比例；
- `Unsupported Evidence Rate`：证据可读取但不能支持 claim 的比例。

### 14.2 用干预信息构造真值，但严防标签泄漏

PAVE 最值得借鉴的是信息隔离协议：

```text
真值构造器：可以读取故障注入、任务 oracle、修复动作
归因方法：只能读取当时可观测证据
评价器：事后比较预测、真值和干预结果
```

这与现有真实运行中“对齐器不读取 ground_truth，事后才核对”的做法一致，应固定为论文级协议。

### 14.3 为候选边建立多重证据门

在执行昂贵的反事实重放前，可以借鉴 PAVE 做低成本筛选：

1. 边类型/系统机制允许；
2. 上下游事件状态存在可解释变化；
3. 单调时钟与因果方向一致；
4. 数据、消息或副作用确实被下游消费；
5. 证据来源和身份映射达到最小完整度。

只有通过这些门的 Top-k 边进入删除、替换或重放。这样既减少成本，也能把“候选定位”和“因果确认”清楚分层。

### 14.4 把“缺失”建模为一等状态

论文发现 killed pod 的 trace silence 会误导 Agent。本课题同样要区分：

```text
healthy：观察到正常行为
missing：预期事件没有出现
unobserved：采集缺口，无法判断
abstain：证据不足，不做责任结论
```

不能把 `no event` 自动映射为 `healthy`，也不能把采集缺口自动变成故障证据。

### 14.5 指标必须分层，不能只报一个 F1

建议最终实验至少同时报告：

- Outcome：任务成功率、责任 Agent/Step/Root Node 的 EM/F1/Top-k/MRR；
- Process：Node F1、Edge F1、Path/Attribution Reachability；
- Verification：反事实翻转率、无关控制误翻转率、重放成功率；
- Evidence：来源指针完整率、证据支持率、身份对齐覆盖率；
- Cost：诊断时延、观测开销、LLM/API 成本和重放次数。

### 14.6 结果必须按结构难度分层

OpenRCA 2.0 证明系统规模和路径深度会改变模型排序。多 Agent 实验至少按以下因素分层：

- Agent 数；
- 决定性步骤位置；
- 传播路径长度；
- 并发/异步程度；
- 单根因、多根因、传播错误和并行症状；
- 证据缺失率；
- 可重放等级 L0-L4。

否则 pooled accuracy 很容易被简单短链样本主导。

## 15. 我相对 OpenRCA 2.0 已具备的优势

这里的“优势”分为已经落地的资产和有潜力但尚未证明的研究优势，不能混写。

### 15.1 已有、可核验的优势（VERIFIED）

| 优势 | 本地证据 | 相对 OpenRCA 2.0 的意义 | 边界 |
|---|---|---|---|
| **面向多 Agent 责任而非微服务组件定位** | [方向 01](../../my_paper/方向框架/01_跨层因果边归因与可验证诊断/README.md) 已定义责任 Agent、Step、Edge 和反事实验证 | 研究对象带有角色、意图、消息、工具和任务判据，能回答“谁的哪一步负决定性责任” | 需要避免把语义责任简单等同于技术故障传播 |
| **已经有五类统一真值协议** | [公开数据适配实验](../../lab/experiment/experiment_20261016_16/实验报告.md) 统一责任 Agent、责任 Step、根因节点、传播边、完整路径 | 可把 outcome 与 process 标签放在同一协议中，且允许 `direct/derived/partial/abstain` | 目前只证明 schema 兼容性，未证明归因方法精度 |
| **跨三个公开归因数据集完成保守适配** | Who&When 184、TRAIL 148、AgentTrace 550，共 882 条全部通过校验；14,697/14,697 关系重建，31,132/31,132 对象具备来源证据 | 数据基础不依赖单一自建 benchmark；能比较 Agent/Step 与 Node/Edge/Path 不同真值强度 | 尚未接入 OpenRCA 2.0，且三个数据集的标签能力不对称 |
| **provenance 与拒答机制已经实现** | 每个非拒绝对象绑定源文件、JSON Pointer、SHA-256 和映射方法；缺失责任语义时主动 abstain | 比“强行补齐过程图”更适合真实 Agent 观测缺失场景 | 还需验证这些字段对实际归因准确率的增量价值 |
| **已有真实 Agent 应用事件与系统观测的跨层身份对齐** | [完整真实进度实验](../../my_paper_coding/trace_adapter/完整真实进度实验报告_2026-10-10.md) 中 3/3 工具事件通过 application session + tool call ID 对齐到同一系统 PID | OpenRCA 主要在 service/pod/span telemetry 内工作；本课题已开始连接 Agent 原生语义与进程级证据 | 目前只有一次受控双 Agent 真实运行，不能声称通用 |
| **已经设计“责任修复 + 无关控制”的反事实接口** | [跨任务 Gate](../../my_paper_coding/evaluation_gate/gate-report.md) 覆盖三任务九次确定性运行；[真实 pilot](../../my_paper_coding/failure_pilot/real-pilot-inventory-report.md) 完成一次离线翻转 | 目标上比 PAVE 的逐边观测门更进一步，可验证候选责任是否决定任务结果 | 真实 Agent 上仍是离线任务判据重放，不是完整 L3 重新执行 |
| **已经把成本和质量门写入实验流程** | 最新进展记录了 API 硬停止线、真实闭环门和扩大样本前条件 | OpenRCA 的 GPT 部分覆盖受预算限制；本课题可把覆盖率和成本显式纳入结论有效性 | 当前预算已限制继续运行，不能把流程纪律写成实验贡献 |

### 15.2 有潜力形成论文差异的优势（INFERRED）

1. **从 fault propagation 扩展到 responsibility propagation。** 微服务边表达技术异常传播；多 Agent 边还需要区分通信、数据、控制、工具契约和环境副作用。责任语义更丰富，也更难。
2. **从完整 telemetry 标注扩展到证据完整度研究。** OpenRCA 明确把 restricted telemetry 评价留给未来工作；本课题的 H1/H2 正在问系统级证据相对消息日志增加多少归因信息，这是一个直接空白。
3. **从“路径看起来成立”扩展到“修复后任务翻转”。** 如果真实 L2/L3 重放完成，本课题可将结构一致的传播路径进一步区分为相关路径与决定性责任路径。
4. **从单一 benchmark schema 扩展到异构归因协议。** 现有 adapter 已经面对不同标签粒度，并显式保留 partial/abstain；这对真实 Agent 数据比假定所有样本都有完整路径更稳健。
5. **把跨层身份本身变成可测误差源。** 当前 H4 已提出请求-响应配对错误会使 Step/Edge 归因退化。OpenRCA 假定 telemetry 已正确落到服务/span；本课题可以实证“观测对齐质量如何改变归因结论”。
6. **把诊断成本纳入 Pareto 分析。** 对比消息日志、完整系统证据和反事实重放的精度、时延、观测开销与费用，可形成比单纯追求最高 F1 更实用的 AgentOps 结论。

### 15.3 尚不能声称的优势（UNVERIFIED）

- 不能声称跨层证据已经提升 Agent/Step/Edge 归因精度；尚未运行完整 B0-B4 方法比较。
- 不能声称反事实方法强于 PAVE；真实 L2/L3 重放和统计样本尚未完成。
- 不能声称方法已跨框架泛化；当前真实闭环主要是 Claude Code + AgentSight attach。
- 不能声称已有大规模多 Agent benchmark；现有 882 条是公开数据适配结果，不等同于 882 条真实跨层 AgentSight 轨迹。
- 不能声称 Step/Edge exact 已验证；最新真实实验明确把二者列为未验证。

## 16. 这篇论文对创新边界的收紧

OpenRCA 2.0 出现后，以下表述不再足以单独构成创新：

- “我们不只预测根因，还预测传播路径”；
- “我们提供节点/边级标签”；
- “我们使用 trace、metric、log 多模态证据”；
- “我们用故障注入自动生成因果过程真值”；
- “我们用 Edge F1/Path Reachability 评价 RCA Agent”。

本课题应把创新稳定在以下组合上：

> **多 Agent 责任语义 + 应用/系统跨层证据 + 可审计身份与 provenance + 证据缺失下的 abstain + 最小反事实验证 + 成本/完整度消融。**

其中任何单项都可能已有相邻工作，但这一组合与 OpenRCA 2.0 的微服务过程 benchmark 有清楚边界。

## 17. 可直接吸收到本课题的方法改造

### 17.1 数据协议映射

建议在现有 schema 中增加或统一以下字段：

```json
{
  "node_state": ["healthy", "anomalous", "missing", "unobserved"],
  "onset_monotonic_ns": 0,
  "alarm_node_ids": [],
  "predicted_path_ids": [],
  "path_reachability": null,
  "edge_support": {
    "structural": null,
    "state_change": null,
    "temporal": null,
    "data_or_control_flow": null,
    "counterfactual": null
  }
}
```

是否实际修改 schema，要先检查现有字段，避免为对齐论文而重复建模。

### 17.2 评价矩阵

建议把下一轮方法比较冻结为：

| 组别 | 输入/方法 | 回答的问题 |
|---|---|---|
| B0 | 最终输出/最终错误节点 | 只看 outcome 能做到什么 |
| B1 | Agent 消息与框架日志 | 语义 trace 能做到什么 |
| B2 | B1 + 工具/环境结果 | 非消息证据提供多少增量 |
| B3 | 完整跨层图 + 结构/时间/数据门 | 低成本过程定位能做到什么 |
| B4 | B3 + Top-k 反事实重放 | 决定性责任验证提供多少增量 |

每组同时报告 Agent/Step/Node/Edge/Path、证据支持和成本，不能只选最有利的指标。

### 17.3 真值质量门

对每个真实多 Agent 失败 case，至少保存：

1. 运行前冻结的故障注入和任务 oracle；
2. 不向归因方法暴露的真值文件；
3. 每条真值边的原始事件指针和时间证据；
4. 至少一个修复责任事件的干预；
5. 至少一个修改无关事件的控制干预；
6. `missing`、`unobserved` 和 `abstain` 的理由；
7. 第二标注者或自动一致性审计记录。

## 18. Claim-Evidence-Gap 表

| ID | Claim | Evidence | 状态 | 对本课题的动作 |
|---|---|---|---|---|
| C1 | PAVE 利用已知注入做前向验证，而不是从症状反推根因 | §2.1，Eq. (1)，p.3 | `VERIFIED` | 固化真值端/归因端信息隔离 |
| C2 | 路径需同时满足结构、统计和时间条件 | §2.2-2.3，Figure 3，pp.3-4 | `VERIFIED` | 用作反事实前的候选边门 |
| C3 | OpenRCA 2.0 有 500 例、3 个系统、27 类 chaos primary kind、平均 7.5 条因果边 | Table 1，p.5 | `VERIFIED` | 与本课题样本规模和路径复杂度对齐 |
| C4 | 11 个模型平均 EM 20.7%、AnySvc 76.0%、PR 61.5% | Abstract；Table 2，pp.1, 6 | `VERIFIED` | 增加 Ungrounded Attribution Rate |
| C5 | 所有模型的 Edge F1 均低于 Node F1，平均差 18.8pp | §3.2，p.6 | `VERIFIED` | Edge 指标必须成为主指标之一 |
| C6 | 主要失败模式包括过早承诺、把缺失当正常、被显著异常吸引 | §3.3，p.7 | `VERIFIED` | 增加 missing/unobserved 状态和跨模态矛盾检查 |
| C7 | 100 例人工审计的 case-level agreement 为 94%，分歧均为保守欠覆盖 | §3.4；Appendix E.1，pp.7-8, 20-21 | `VERIFIED` | 真值应优先高精度，并报告路径欠覆盖 |
| C8 | 完整 telemetry 只在标注时必需，之后可用同一真值评价受限观测 Agent | §5，p.9 | `VERIFIED` | 直接支持 B1/B2/B3 证据消融设计 |
| C9 | PAVE 已独立证明每条边的反事实因果性 | 论文没有逐边删除/重放实验 | `UNVERIFIED` | 本课题不得把三重观测门等同于 L2/L3 干预 |
| C10 | 本课题跨层证据比消息日志显著提高 Edge F1 | 尚无 B0-B4 完整结果 | `UNVERIFIED` | 下一阶段核心可证伪假设 |
| C11 | 现有统一协议可承载异构 Agent/Step/Node/Edge/Path 标签 | 882 条公开记录全部校验通过 | `VERIFIED`（协议兼容性） | 接入 OpenRCA 2.0 时保持 source pointer 与 abstain |
| C12 | 反事实重放可在真实多 Agent 开放任务中稳定验证责任 | 当前只有确定性 gate 和单条真实运行的离线翻转 | `UNVERIFIED` | 完成两次真实多 Agent 闭环和真实 L2/L3 replay |

## 19. 可用于相关工作的短评草稿

OpenRCA 2.0 将微服务 RCA 的监督信号从根因结果标签扩展到节点、边和路径级过程标签。其 PAVE 协议利用已知故障注入，从根因向下游执行结构、基线偏离和时间一致性的联合验证，并在三个微服务系统上构造了 500 个过程级实例。该基准显示，LLM 即使能够命中正确服务，也经常无法给出连接根因与症状的有效传播路径，且 Edge F1 显著低于 Node F1。这说明根因定位与传播推理必须分开评价。与该工作不同，本课题关注 LLM 多 Agent 任务中的责任传播，将消息、工具、模型调用与系统副作用对齐为跨层执行证据，并进一步以任务级删除、替换或重放检验候选责任边；因此研究重点不是复现微服务传播标签，而是评估跨层证据和反事实验证对 Agent/Step/Edge 责任归因的增量价值。

## 20. 下一研究闸门

### 可以立即决定的事项

1. **保留方向 01，但收紧贡献表述。** 主张必须从“有因果路径”升级为“多 Agent 跨层责任路径及其反事实验证”。
2. **把 OpenRCA 2.0 纳入最强相邻基线。** 它不是直接任务基线，但必须是过程真值、Edge F1 和 path reachability 的方法学对照。
3. **下一版评价代码加入 ungrounded attribution。** 分开记录“Agent/Step 命中”和“路径/验证成立”。
4. **继续使用保守真值。** 对没有直接标签或可验证边的样本保持 `partial/abstain`，不要补造完整路径。

### 缺失证据

- OpenRCA 2.0 完整公开 artifact 和 PAVE 代码尚未在本仓库核验；
- 尚无真实多 Agent B0-B4 归因准确率比较；
- 尚无真实运行中的 Step/Edge exact；
- 尚无 L2/L3 级真实重放和无关控制的统计结果；
- 尚无第二 Agent 框架和并发/异步场景。

### 推荐的下一步

先完成两次真实多 Agent 闭环，并在同一批 case 上固定报告：

```text
Agent/Step 命中
+ Node/Edge F1
+ Attribution Reachability
+ 反事实翻转与无关控制
+ provenance/身份对齐覆盖
+ 时延与成本
```

只有当完整跨层证据相对消息日志在 Edge F1、Attribution Reachability 或反事实验证率上出现稳定提升，才能把“跨层证据带来增量价值”从 `INFERRED` 升级为 `VERIFIED`。

## 21. AUTHOR_INPUT_NEEDED

需要作者本人最终确认一个论文定位选择：

- **方法型路线**：强调新的跨层候选排序与反事实验证算法，需要足够真实样本和强 baseline；
- **实证型路线**：强调证据完整度、身份对齐误差和重放成本如何改变归因结论，算法可以相对简单，但实验设计必须更强。

基于当前已有资产，推荐优先采用“实证主线 + 可验证归因方法”的组合：先证明跨层证据何时有用、何时会误导，再把反事实模块作为提高可信度的关键机制。这样既避开与 OpenRCA 2.0 在“过程级 benchmark”上的正面重复，也能最大化利用现有 AgentSight、统一 adapter、provenance 和真实运行闭环。
