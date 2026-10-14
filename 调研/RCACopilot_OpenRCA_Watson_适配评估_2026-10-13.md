# RCACopilot、OpenRCA、Watson 与当前论文方向的适配评估

检索日期：2026-10-13。检索问题：这三项工作能否支持“面向 LLM 多智能体失败的跨层执行证据图、责任边定位与可执行验证”。优先使用论文正文、官方项目页、正式会议记录和本地复现实验。

## 检索结论

| 工作 | 正式信息 | 它真正解决的问题 | 对当前论文的适配度 | 建议角色 |
|---|---|---|---|---|
| RCACopilot | Chen et al., *Automatic Root Cause Analysis via Large Language Models for Cloud Incidents*, EuroSys 2024, DOI `10.1145/3627703.3629553` | 用按告警类型配置的 incident handler 收集多源诊断信息，再用历史案例检索、CoT 和 LLM 预测根因类别并生成解释 | 中 | `supporting`：工业流程、证据收集和人机协同参考；不作为边级因果算法基线 |
| OpenRCA | Xu et al., *OpenRCA: Can Large Language Models Locate the Root Cause of Software Failures?*, ICLR 2025 | 用 335 个企业系统故障和 68.5 GB 日志/指标/Trace，评测 LLM 输出根因时间、组件和原因；RCA-agent 用程序合成与执行查询遥测 | 高 | `core`：任务定义、结构化输出、程序化证据检索和评测基线 |
| Watson | Rombaut et al., *Watson: A Cognitive Observability Framework for the Reasoning of LLM-Powered Agents*, ASE 2025, DOI `10.1109/ASE63991.2025.00067` | 在不修改主 Agent 的条件下，旁路重建并验证可能的隐式推理轨迹 | 高，但用途不同 | `supporting/core-observation`：认知证据候选；不得作为责任或因果真值 |
| OpenRCA 2.0 | Fang et al., *OpenRCA 2.0: From Outcome Labels to Causal Process Supervision*, arXiv:2606.27154, 2026 | 用已知故障注入和 PAVE 前向验证构建逐步因果传播路径，评价根因、节点、边和路径 | 很高 | `core`：当前最接近“责任边 + 可验证路径”的工作，也是创新性压力来源 |

名称消歧：检索到另一篇 2025 年预印本 *RCA Copilot: Transforming Network Data into Actionable Insights via Large Language Models*（arXiv:2507.03224）。本文按社区通常所指的 EuroSys 2024 `RCACopilot` 进行主分析；2025 网络版本更偏网络运维，和多智能体责任归因的距离更远。

## 逐篇判断

### 1. RCACopilot：能帮助工程设计，不能直接支撑论文的核心因果主张

**VERIFIED**

- 数据是微软 Transport 服务一年的 653 个事故，按 75%/25% 划分训练与测试；人工根因类别作为真值。
- GPT-4 版本报告 Micro-F1 0.766、Macro-F1 0.533，平均推理时间 4.205 秒；诊断信息收集模块已在微软约 30 个团队使用超过四年。
- 核心机制是 `alert type → incident handler → multi-source diagnostic information → historical case retrieval/CoT → root-cause category + explanation`。

**对当前工作的价值**

1. 可以把当前 Trace Adapter 的不同证据采集器设计成类似 incident handler 的可组合动作，但入口应由“故障场景/证据需求”驱动，而不是只按告警类型驱动。
2. 可以增加一个弱基线：把统一事件摘要交给 LLM，输出 Agent/Step/Reason；它代表“仅分类和解释”的工业 RCA 路线。
3. 它的多源证据消融和人工复核流程可用于论文系统评测。

**不应迁移的部分**

- 根因类别预测不是传播边归因；自然语言解释也不是因果证据。
- 私有事故数据和服务专用 handler 限制了可复现性和外部效度。
- 它没有用局部重放或干预验证“该根因导致了该失败”。

### 2. OpenRCA：最适合借鉴任务与评测外壳

**VERIFIED**

- 原始基准包含 Telecom、Bank、Market 三个企业系统的 335 个故障、73 个根因组件、28 个根因原因和 68.5 GB 遥测。
- 结构化根因由 `occurrence time + component + reason` 组成；335 条记录经过 3 名有经验工程师校准，不可由遥测支持的记录被剔除。
- Claude 3.5 在 oracle telemetry 下准确率为 5.37%，平衡采样为 3.88%；RCA-agent 通过 Python 查询遥测后达到 11.34%。
- RCA-agent 的关键不是“多 Agent”这个形式，而是让 LLM 编写和执行查询代码，避免把海量非自然语言遥测直接塞入上下文。

**对当前工作的直接价值**

1. 统一归因输出建议至少包含 OpenRCA 的 `time/component/reason`，再扩展为 `agent/step/edge/evidence/confidence/verification`。
2. 归因模型只读取证据索引和查询结果；原始系统事件由工具按需查询。这与当前 provenance graph 和证据引用设计兼容。
3. 评测必须把根因组件、发生时间、原因分开报告，不能只报一个总体 exact match。
4. 可以将 RCA-agent 作为“程序化证据检索”对照，但 OpenRCA 全量复现要求约 80 GB 存储和 32 GB 内存，当前没有必要立刻下载 68.5 GB 数据集。

**边界**

- OpenRCA 1.0 的真值主要是最终根因元素，不提供完整传播边真值。
- 对象是微服务与基础设施故障，不是多智能体中的责任、消息误导、工具静默错误或角色/路由错误。

### 3. Watson：适合作为昂贵的认知证据通道

**VERIFIED**

- Watson 用 FIM/RepCoT 旁路生成候选推理，再用提示归因与 LLM judge 过滤；每个实例生成 10 条合格推理。
- 论文覆盖 MMLU、AutoCodeRover 和 OpenHands；在代码 Agent 上观察到的提升没有达到统计显著。
- 本地已经完成可审计的近似 RepCoT 流程、16 组离线控制实验和两个 DeepSeek API 小样例。

**对当前工作的正确用法**

- 当系统证据已把候选范围缩小到某个 Agent/Step 后，按需触发 Watson，生成“为什么该步骤可能如此决策”的认知证据候选。
- Watson 结果应记录为 `inferred`，并进入后续重放/反事实验证；不能把重建推理直接写成真实隐藏 CoT。
- 主实验需要比较“无 Watson”和“加入 Watson 候选”的定位增益、费用、延迟和错误率。

**主要风险**

- 推理重建忠实性仍依赖代理模型、提示归因和 LLM judge，存在循环验证风险。
- 10 条候选、归因和 judge 的 API 成本高，不适合作为每条事件都执行的基础观测层。

### 4. OpenRCA 2.0：对当前创新点有直接影响

**VERIFIED**

- PAVE 从已知故障注入 `do(v_root)` 出发，先按拓扑和传播规则筛选路径，再用注入前后遥测联合检查统计偏移和时序对齐。
- 基准包含 3 个微服务系统、500 个实例和 27 类故障；每条样本带服务、Pod、Span 上的逐步传播图。
- 输出包含根因主张和传播边，并要求每条证据关联可重新执行的 SQL 查询。
- 论文报告两位作者对随机 100 条样本进行审计，案例级一致率为 94%。
- 其评价已经显式包含 Node-F1、Edge-F1、传播路径正确性以及“命中根因但没有正确路径”的 ungrounded diagnosis。

**对论文方向的影响**

OpenRCA 2.0 已经覆盖“传播边真值、逐步因果路径、干预驱动前向验证、Edge-F1”。因此，当前论文不能再把“提出可验证的边级传播图”本身作为新颖性主张。仍可成立的差异是：

1. **研究对象不同**：多智能体协作责任，而不是微服务资源故障传播；
2. **证据层次不同**：把消息、工具调用、模型调用、进程、文件和网络统一到 Agent/Step 身份；
3. **责任语义不同**：区分产生错误、传播错误、未拦截错误和放大错误；
4. **验证操作不同**：局部重放、替换消息/工具结果、剪除通信边或替换 Agent 决策，而不是仅依赖基础设施故障注入；
5. **观测不确定性显式化**：PID 映射、时钟界和缺失证据可以 abstain，不把时间相关性升级成因果关系。

## Claim–Evidence 映射

| Claim | Evidence | 可用于论文的位置 | 状态 |
|---|---|---|---|
| 多源证据收集本身是 RCA 系统的重要组成部分 | RCACopilot 的 handler、消融和生产部署 | 系统设计、工业动机 | `VERIFIED` |
| 海量遥测应通过程序化查询而不是全部进入 LLM 上下文 | OpenRCA 的 RCA-agent | 方法设计、成本分析 | `VERIFIED` |
| 只预测最终根因会掩盖错误的诊断过程 | OpenRCA 2.0 的 ungrounded diagnosis 与路径指标 | 研究问题、评测指标 | `VERIFIED` |
| 认知重建可补充运行时行为证据 | Watson 的旁路推理重建与案例 | 可观测性分层、扩展实验 | `VERIFIED` |
| 上述微服务方法可以直接证明多智能体责任 | 三篇均未提供该证据 | 不得作此主张 | `UNVERIFIED` |

## 建议的使用优先级

1. **立即精读并对齐 OpenRCA 2.0**：把当前图 schema 和评价指标逐项映射到 root/node/edge/path/evidence-query。
2. **吸收 OpenRCA 1.0 的任务外壳**：建立 `time + agent/component + reason + step + edge` 的结构化答案和分字段指标。
3. **保留 Watson 为按需模块**：等身份/工具 provenance graph 稳定后再接入，避免认知候选污染基础观测真值。
4. **RCACopilot 作为工业与弱基线参考**：不投入复现其私有分类任务。

## 下一研究闸门

在开始归因算法前，完成一张“本论文 schema vs OpenRCA 2.0 schema”的字段与指标对照表，并回答：哪些 Agent 责任边无法用服务传播边表达？只有该差异能够被明确标注和执行验证，当前方向才保有清晰的新颖性。

## 来源

- [RCACopilot / arXiv](https://arxiv.org/abs/2305.15778)；[DBLP / EuroSys 2024](https://dblp.org/rec/conf/eurosys/ChenXMKGSCGFWZG24.html)
- [OpenRCA / ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/d29b8d53678015079e1d245c023e49d2-Abstract-Conference.html)；[官方代码](https://github.com/microsoft/OpenRCA)
- [Watson / IEEE Xplore](https://ieeexplore.ieee.org/abstract/document/11334632/)；[arXiv](https://arxiv.org/abs/2411.03455)
- [OpenRCA 2.0 / arXiv](https://arxiv.org/abs/2606.27154)
