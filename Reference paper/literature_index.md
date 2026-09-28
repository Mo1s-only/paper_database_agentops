# AgentOps 文献总索引与证据地图

检索截止日期：2026-09-23。完整来源链接和文件级说明见各分类目录的 `README.md`。

状态：`core` = 论文主线必须引用；`supporting` = 支撑方法或背景；`contrast` = 用于建立边界；`candidate` = 已下载、待精读。证据状态使用 `VERIFIED`、`INFERRED`、`UNVERIFIED`。

## 主索引

| ID | 论文 | 主分类 | Venue/年份 | 级别与证据状态 | 一句话论文概要 | 研究用途 | 本地文件 |
|---|---|---|---|---|---|---|---|
| R01 | AgentMonitor | 观测/预测 | arXiv 2024 | 预印本；`VERIFIED` | 从Agent输入输出和图属性预测MAS任务表现并进行在线安全修正 | 预测性监控、运行指标候选 | `01_agent_observation/AgentMonitor.pdf` |
| R02 | AgentSight | 系统观测 | PACM@SOSP Workshop 2025 | Workshop；`VERIFIED` | 用eBPF关联模型语义活动与系统级行为 | 论文的零侵入观测基线 | `01_agent_observation/AgentSight.pdf` |
| R03 | AgentTrace | 根因追踪 | ICLR 2026 Agents in the Wild Workshop | Workshop；`VERIFIED` | 将Agent事件构造成因果图并排序根因节点 | 日志重建式追踪对照 | `01_agent_observation/AgentTrace_Causal_Graph_Tracing.pdf` |
| R04 | Information Propagation Effects | 通信观测 | arXiv 2025 | 预印本；`VERIFIED` | 分析通信拓扑对正确与错误信息传播的影响 | 通信边和拓扑效应指标 | `01_agent_observation/Understanding the Information.pdf` |
| R05 | Which Agent Causes Task Failures and When? | 故障归因 | ICML 2025 | 顶级会议主会；`VERIFIED` | 定义Agent级与步骤级自动故障归因任务和Who&When数据集 | 核心归因基准 | `02_failure_attribution/Which Agent Causes Task Failures and When.pdf` |
| R06 | Seeing the Whole Elephant / TraceElephant | 故障归因 | ACL 2026 | 顶级会议主会；`VERIFIED` | 用完整执行轨迹与可复现实验环境评估故障归因 | 全可观测性与归因性能证据 | `02_failure_attribution/TraceElephant_Seeing_the_Whole_Elephant.pdf` |
| R07 | Why Do Multi-Agent LLM Systems Fail? / MAST | 失败分类 | NeurIPS 2025 D&B Track | 顶级会议；`VERIFIED` | 建立多智能体失败分类法和1600余条标注轨迹 | 失败标签体系与数据集 | `02_failure_attribution/MAST_Why_Do_Multi_Agent_LLM_Systems_Fail.pdf` |
| R08 | CDC-MAS | 因果归因 | arXiv 2025；PDF显示AAAI版权 | 正式会议信息待独立核验；`INFERRED` | 用性能因果反转、Shapley值和因果发现定位Agent与步骤 | 因果归因方法对照 | `02_failure_attribution/CDC-MAS_Automatic_Failure_Attribution.pdf` |
| R09 | EDGE | 多错误归因 | arXiv 2026 | 预印本；`VERIFIED` | 构造并以反事实重放验证错误依赖图 | 边级错误传播的重要对照 | `02_failure_attribution/EDGE_Error_Dependency_Graph.pdf` |
| R10 | Watson | 认知诊断 | ASE 2025 | 顶级软件工程会议；`VERIFIED` | 恢复并检查LLM Agent隐式推理轨迹 | 认知可观测性对照 | `03_diagnosis_localization/Watson.pdf` |
| R11 | eInfer | 系统追踪 | eBPF@SIGCOMM 2025 | Workshop；`VERIFIED` | 用eBPF对分布式LLM推理进行细粒度跨层追踪 | 系统层实现与开销基线 | `03_diagnosis_localization/eInfer.pdf` |
| R12 | Beyond Natural Language | 通信诊断 | Findings of EMNLP 2024 | Findings；`VERIFIED` | 比较自然语言与结构化格式的推理、通信效率 | 消息格式和通信成本指标 | `03_diagnosis_localization/Beyond Natural Language.pdf` |
| R13 | Tools Fail | 工具错误诊断 | EMNLP 2024 | 重要会议主会；`VERIFIED` | 检测工具静默错误并研究错误对Agent执行的影响 | 工具层错误检测指标 | `03_diagnosis_localization/Tools_Fail_Detecting_Silent_Errors_in_Faulty_Tools_EMNLP2024.pdf` |
| R14 | AgentDropout | 预测/优化 | ACL 2025 | 顶级会议主会；`VERIFIED` | 动态消除冗余Agent和通信边以降低token成本 | 拓扑干预、效率与效果指标 | `04_prediction_early_warning/AgentDropout.pdf` |
| R15 | Breaking Agents | 风险预警 | EMNLP 2025 | 重要会议主会；`VERIFIED` | 通过故障放大攻击使Agent重复或偏离任务 | 攻击成功率、异常循环与防御指标 | `04_prediction_early_warning/Breaking_Agents_Malfunction_Amplification_EMNLP2025.pdf` |
| R16 | DistServe | 服务可靠性 | OSDI 2024 | 顶级系统会议；`VERIFIED` | 分离prefill与decode并以TTFT、TPOT约束下goodput评价服务 | 系统负载与SLO对照 | `05_reliability_evaluation/DistServe.pdf` |
| R17 | AgentEval | 任务效用 | EMNLP 2024 | 重要会议主会；`VERIFIED` | 自动提出应用特定评价准则并量化任务效用 | 开放任务多维效用评价 | `05_reliability_evaluation/Assessing_and_Verifying_Task_Utility_in_LLM-Powered_Applications_EMNLP2024.pdf` |
| R18 | AgentBench | 通用Agent评测 | ICLR 2024 | 国际机器学习顶会主会；`VERIFIED` | 在八类交互环境中统一评价LLM作为Agent的能力 | 通用任务成功率基线 | `06_agent_evaluation_metrics/AgentBench_ICLR2024.pdf` |
| R19 | AgentBoard | 过程评测 | NeurIPS 2024 D&B Track | 顶级会议；`VERIFIED` | 用细粒度进展率补充最终成功率 | 过程级指标核心来源 | `06_agent_evaluation_metrics/AgentBoard_NeurIPS2024.pdf` |
| R20 | τ-bench | 可靠性评测 | ICLR 2025 | 国际机器学习顶会主会；`VERIFIED` | 用最终数据库状态和`pass^k`评价工具Agent的稳定完成能力 | 重复运行可靠性核心来源 | `06_agent_evaluation_metrics/TauBench_ICLR2025.pdf` |
| R21 | LLMArena | 动态多Agent评测 | ACL 2024 | 顶级会议主会；`VERIFIED` | 在动态竞争/协作环境中测量对手建模和团队协作 | 多智能体能力维度 | `06_agent_evaluation_metrics/LLMArena_ACL2024.pdf` |
| R22 | MultiAgentBench | 协同评测 | ACL 2025 | 顶级会议主会；`VERIFIED` | 使用动态里程碑KPI比较协作、竞争和通信拓扑 | 系统协同层指标核心来源 | `06_agent_evaluation_metrics/MultiAgentBench_ACL2025.pdf` |
| R23 | DREAM | Agent化评测 | ACL 2026 | 顶级会议主会；`VERIFIED` | 结合固定指标和工具Agent生成的自适应指标评价深度研究Agent | 事实性、时效性与覆盖率评价 | `06_agent_evaluation_metrics/DREAM_ACL2026.pdf` |

## Claim–Evidence视图

| 论文主张 | 主要证据 | 可支撑的论文论点 | 当前缺口 |
|---|---|---|---|
| 完整轨迹能提高细粒度归因能力 | R05、R06 | 可观测性是可靠故障归因的必要条件 | 尚缺系统调用/网络边相对应用日志的增益实验 |
| 多智能体失败具有结构性和传播性 | R07、R08、R09 | 仅评价最终答案不能解释失败来源 | 边级责任标签和统一传播指标仍不足 |
| 通信拓扑影响性能、成本和错误扩散 | R04、R14、R22 | 拓扑既是评价对象，也是可干预变量 | 需要控制Agent能力和任务难度的消融实验 |
| Agent评价应同时覆盖结果、过程与稳定性 | R18、R19、R20、R22 | 成功率应与进展率、pass^k、里程碑KPI联合报告 | 各指标跨任务的可比性仍需定义 |
| 生产级Agent评价必须包含系统负载和成本 | R02、R11、R16 | 语义正确性与TTFT、TPOT、goodput、token成本应联合分析 | 尚缺面向多Agent关键路径的SLO指标 |
| LLM-as-a-Judge需要可校准和可审计 | R07、R17、R23 | 自动评测器不能直接视为绝对真值 | 需要人类一致性、偏差和置信区间报告 |

## 当前优先级

1. `core`：R02、R05、R06、R07、R09、R19、R20、R22。
2. `supporting`：R01、R03、R04、R08、R10、R11、R13、R14、R17、R23。
3. `contrast`：R12、R15、R16、R18、R21。

下一道研究关口：精读R19、R20、R22，统一“任务成功—过程进展—重复稳定—协同质量”的分母、统计粒度和聚合方法，再与R05/R06的Agent级、Step级归因准确率连接起来。
