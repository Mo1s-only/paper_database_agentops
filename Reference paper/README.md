# AgentOps 文献库

本目录服务于 AgentOps、多智能体系统监控、执行追踪、故障诊断与归因研究。分类依据是论文在“运行—失败—诊断—评价”链路中主要解决的问题，而不是按模型、作者或年份分类。

## 分类结构

```text
运行观测 → 故障归因 → 诊断定位 → 预测/预警 → 可靠性评价
                                      ↘ Agent 评价指标（横向评价层）
```

| 目录 | 核心问题 | 典型证据 |
|---|---|---|
| `01_agent_observation/` | 如何采集 Agent、工具、模型和系统层运行证据？ | trace、日志、eBPF、通信拓扑、认知可观测性 |
| `02_failure_attribution/` | 哪个 Agent、步骤或传播关系导致最终失败？ | Agent/Step 准确率、MRR、Hit@k、反事实验证、错误依赖图 |
| `03_diagnosis_localization/` | 如何检测异常并定位工具、推理或系统根因？ | 静默错误检测、根因定位、调试与跨层追踪 |
| `04_prediction_early_warning/` | 能否在任务完成前预测失败或抑制风险传播？ | 风险分数、掉队/冗余识别、攻击成功率、提前预警 |
| `05_reliability_evaluation/` | 系统是否稳定、高效并满足任务效用或SLO？ | task utility、TTFT、TPOT、goodput、资源与成本 |
| `06_agent_evaluation_metrics/` | 如何建立可复现的 Agent/多智能体评价协议？ | 成功率、进展率、pass^k、里程碑KPI、协作/竞争质量 |
| `99_cross_cutting/` | 跨分类综合和差异化分析 | 对比矩阵、研究缺口、方法继承关系 |

每个分类目录内的 `README.md` 是该目录的来源台账，记录论文页面、PDF来源、会议/期刊及发表级别。根目录的 `literature_index.md` 是跨目录的主索引和简要证据地图。

## 会议与发表级别说明

本库不使用未经说明的笼统“顶会论文”标签，统一记录以下状态：

- **顶级会议主会**：如 ACL、NeurIPS、ICML、OSDI、ASE；其中 Datasets and Benchmarks Track 需单独注明。
- **重要会议主会**：如 EMNLP；如采用 CCF 口径，ACL、NeurIPS、ICML、OSDI、ASE 通常记为 CCF-A，EMNLP 记为 CCF-B。
- **Findings**：ACL 系列的独立论文集，不等同于同名会议主会。
- **Workshop/Demo**：研讨会或系统演示论文，不等同于主会长文。
- **arXiv/preprint**：预印本；除非找到会议官方页面或正式出版记录，否则不宣称已被顶会录用。

“级别”只描述发表载体，不等价于论文质量或与本课题的相关性。

## 文件约定与证据状态

- 原始论文使用 `.pdf`；论文来源以分类目录 `README.md` 中的官方页面为准。
- 文件名含 `(Chain)` 或 `(Chian)` 的资料不作为独立论文计数，其生成方式和完整性尚未统一核验。
- `AgentOps.pdf` 与 `AgentSight.pdf` 实际均为 *AgentSight: System-Level Observability for AI Agents Using eBPF*，是不同版本的重复副本；暂保留文件，索引只计一篇。
- `VERIFIED`：已由会议/出版社、ACL Anthology、PMLR、USENIX、ACM/IEEE DOI、OpenReview正式接收页或论文正文核验。
- `INFERRED`：由论文正文或作者材料推断，但缺少独立正式出版页面。
- `UNVERIFIED`：仅有文件名、笔记或二手描述，不能用于确定发表状态。

## 本轮新增的评价指标论文

`06_agent_evaluation_metrics/` 新增并保存六篇源论文：

1. AgentBench — ICLR 2024；统一的多环境Agent能力评价。
2. AgentBoard — NeurIPS 2024 Datasets and Benchmarks Track；过程进展率。
3. τ-bench — ICLR 2025；工具—Agent—用户交互与 `pass^k` 可靠性。
4. LLMArena — ACL 2024；动态多智能体环境中的竞争与协作能力。
5. MultiAgentBench — ACL 2025；里程碑KPI与不同通信拓扑评价。
6. DREAM — ACL 2026；使用Agent化评测器评估深度研究Agent。

## 检索记录

- 本轮核验与下载日期：2026-09-23。
- 主要来源：ACL Anthology、NeurIPS Proceedings、PMLR、OpenReview、USENIX、ACM Digital Library、IEEE Xplore、arXiv。
- 纳入原则：与 Agent 评价指标、运行观测、故障归因或系统可靠性直接相关；优先正式主会论文；必须有可追溯的论文页面或原始PDF。
- 排除原则：只有博客或榜单、无法核验论文身份、只评价基础模型且不能映射到 Agent 运行过程的材料。

下一道研究关口：把 `06_agent_evaluation_metrics/` 中的成功率、过程进展率、`pass^k`、里程碑KPI、成本和安全指标映射到 `my_paper/metric/`，并明确哪些指标是文献继承、哪些是本文针对边级故障归因的新定义。
