# 06 Agent Evaluation Metrics：来源、级别与指标贡献

本目录集中收录直接定义Agent/多智能体评价任务、指标或评测协议的论文。六篇源论文均已保存为PDF。

| 论文 | 本地PDF | 论文页/下载来源 | Venue/年份 | 级别 | 主要指标或评价设计 |
|---|---|---|---|---|---|
| AgentBench: Evaluating LLMs as Agents | `AgentBench_ICLR2024.pdf` | [OpenReview会议页](https://openreview.net/forum?id=zAdUB0aCTQ)；[arXiv下载源](https://arxiv.org/abs/2308.03688) | ICLR 2024 | 国际机器学习顶会主会 | 多环境任务成功率、环境归一化得分、交互式Agent能力 |
| AgentBoard: An Analytical Evaluation Board of Multi-turn LLM Agents | `AgentBoard_NeurIPS2024.pdf` | [NeurIPS论文页](https://proceedings.neurips.cc/paper_files/paper/2024/hash/877b40688e330a0e2a3fc24084208dfa-Abstract-Datasets_and_Benchmarks_Track.html)；[官方PDF](https://proceedings.neurips.cc/paper_files/paper/2024/file/877b40688e330a0e2a3fc24084208dfa-Paper-Datasets_and_Benchmarks_Track.pdf) | NeurIPS 2024 Datasets and Benchmarks Track | 顶级会议 | 成功率与细粒度Progress Rate，支持多轮过程分析 |
| τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains | `TauBench_ICLR2025.pdf` | [OpenReview会议页](https://openreview.net/forum?id=roNSXZpUDN)；[arXiv下载源](https://arxiv.org/abs/2406.12045) | ICLR 2025 | 国际机器学习顶会主会 | 最终数据库状态匹配、策略遵循、`pass^k`重复运行可靠性 |
| LLMArena: Assessing Capabilities of Large Language Models in Dynamic Multi-Agent Environments | `LLMArena_ACL2024.pdf` | [ACL Anthology](https://aclanthology.org/2024.acl-long.705/)；[官方PDF](https://aclanthology.org/2024.acl-long.705.pdf) | ACL 2024 Long Paper | 顶级会议主会 | 动态环境中的竞争、协作、对手建模与团队能力 |
| MultiAgentBench: Evaluating the Collaboration and Competition of LLM Agents | `MultiAgentBench_ACL2025.pdf` | [ACL Anthology](https://aclanthology.org/2025.acl-long.421/)；[官方PDF](https://aclanthology.org/2025.acl-long.421.pdf) | ACL 2025 Long Paper | 顶级会议主会 | 动态里程碑KPI、任务分数、协作/竞争质量、拓扑比较 |
| DREAM: Deep Research Evaluation with Agentic Metrics | `DREAM_ACL2026.pdf` | [ACL Anthology](https://aclanthology.org/2026.acl-long.448/)；[官方PDF](https://aclanthology.org/2026.acl-long.448.pdf) | ACL 2026 Long Paper | 顶级会议主会 | 固定指标与Agent生成的自适应指标，评价事实性、时效性、覆盖和推理 |

## 与论文指标体系的映射

| 层次 | 可继承设计 | 主要来源 |
|---|---|---|
| 任务结果层 | Task Success、环境状态匹配、归一化任务得分 | AgentBench、τ-bench |
| 过程层 | Progress Rate、里程碑完成率、关键步骤完成率 | AgentBoard、MultiAgentBench |
| 稳定性层 | `pass^k`、多次运行方差、失败类型分布 | τ-bench |
| 协同层 | 协作/竞争质量、拓扑差异、团队能力 | LLMArena、MultiAgentBench |
| 评测器质量层 | 事实核验、时效性、覆盖率、自适应评测器敏感性 | DREAM |

注意：这些论文主要评价Agent任务表现和过程质量，并未形成对“span间因果边归因质量”的统一指标；边级Precision/Recall、关键传播边Hit@k和反事实修复增益仍需要在论文中单独定义并验证。
