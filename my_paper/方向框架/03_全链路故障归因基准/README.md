# 方向 03：全链路多智能体故障归因基准

## 一句话定位

构建一个同时包含任务、Agent 输入输出、工具/环境交互、系统副作用、配置、可重放环境和 Agent/Step/Edge 真值的多智能体故障归因基准，并研究不同可观测性假设会导出怎样不同的评价结论。

## 为什么有价值

- Who&When 建立了 Agent/Step 归因任务；TraceElephant 强调完整执行轨迹；MAST 提供失败分类法。
- 本仓库已有 AgentSight 的系统级信号和 Watson 的诊断输入需求，可以补上“语义 trace 与真实系统效果对齐”的数据层。
- NeurIPS 2026 Evaluations & Datasets Track 明确欢迎评价协议、基准审计、可复现评测和负结果。

## 与现有工作的边界

AgentChaos 已提供运行时非侵入式 LLM API 故障注入，因此本方向不能只发布一个注入器。差异应落在：

- 多层证据包，而非只有注入配置和任务结果；
- Agent/Step/Edge/传播路径多粒度真值；
- 可观测性级别作为实验变量；
- 可重放、许可、隐私和标注质量的完整协议。

## 预期贡献

- C1：面向 AgentOps 的失败与证据 schema。
- C2：带可执行真值和可重放环境的数据集。
- C3：可观测性条件、评测任务、指标和强基线套件。
- C4：对现有归因方法的审计，揭示结论对证据缺失和标注协议的敏感性。

## 对标类型与层次

- 冲刺：NeurIPS Evaluations & Datasets、ACL（CCF A 类），适合高质量数据/评价科学贡献。
- 主攻：EMNLP（CCF B 类）或相应 Findings/资源 Track，强调语言交互与 trace 评价。
- 软件工程路线：ESEM、ISSRE（CCF B 类），强调可复现评测与可靠性。
- 数据未成规模时：Workshop/Benchmark Track，不应声称完整基准。

## 当前成熟度

`UNVERIFIED / 高投入`。已有数据来源和 schema 线索，但没有达到发布要求的数据规模、许可、双人标注与稳定重放环境。

## Go / No-Go

- Go：能冻结至少 3 类系统、5 类故障、可重复重放的 trace，并达到可靠标注一致性。
- No-Go：数据无法合法公开、环境不可重放或真值主要依赖单个 LLM judge；转为方向 05 的受限实证研究。
