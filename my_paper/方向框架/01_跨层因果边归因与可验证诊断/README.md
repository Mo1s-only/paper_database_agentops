# 方向 01：跨层因果边归因与可验证诊断

## 一句话定位

面向 LLM 多智能体任务失败，把消息、工具、进程、文件、网络和模型调用统一为带类型的执行证据图，定位“哪个 Agent 的哪个步骤通过哪条责任边导致失败”，并用局部重放或反事实干预验证诊断。

## 为什么最契合现有工作

- AgentSight 已提供系统行为证据，Watson 已提供受约束的旁路诊断原型。
- Who&When/TraceElephant 提供 Agent/Step 归因任务，EDGE/AgentTrace 提供图与传播思路。
- `my_paper/metric/` 已经围绕 CERA 整理边级归因、任务、过程、修复和成本指标。

## 核心差异化

当前不能再把“跨层 RCA”本身当作创新，因为 TELLER 已在 ASE 2026 覆盖 LLM 推理服务的跨层 RCA。本方向必须同时满足三点：

1. 对象是多智能体协作中的责任与传播，而不是 GPU 推理栈异常；
2. 输出包含责任 Agent、步骤、边、证据区间和置信度，而不只是自然语言解释；
3. 用可执行反事实或局部重放验证责任，而不把相关性排序当作因果结论。

## 预期贡献

- C1：多智能体跨层执行证据模型与责任边类型学。
- C2：分层候选定位 + 反事实验证的归因算法。
- C3：证据完整度、边类型和故障传播对归因效果的系统实验。
- C4（可选）：诊断驱动的安全重试/隔离，仅作为外部效度验证，不扩张成完整自治修复论文。

## 对标类型与层次

- 冲刺：ASE、ICSE、FSE（软件工程 CCF A 类），适合“新方法 + 可用系统 + 强实证”。
- 高风险 AI 路线：ICML/NeurIPS（CCF A 类），前提是因果问题与方法创新足够强，而非工程集成。
- 期刊扩展：TSE/TOSEM（CCF A 类），需增加多框架、纵向运行或用户调试实验。
- 早期版本：Agent/SE Workshop，只适合方法尚未完成或样本规模很小时。

## 当前成熟度

`INFERRED / 观测—适配—归因—反事实的单案例闭环已打通，真实多故障泛化尚待验证`。目前已完成受控 marker 配对、AgentSight attach 模式、两 Agent 同 session 观测、统一 trace 归一化、三类确定性故障矩阵，以及 1 条真实 `inventory-silent-tool` pilot。真实 pilot 的事件语义仍部分依赖受控 workspace artifact，尚未形成跨任务、跨框架的独立真值数据集。

当前证据位置：

- `my_paper_coding/p0_pairing/pilot-summary.md`：5 条受控调用，配对 Precision/Recall 均为 1.000；
- `my_paper_coding/failure_pilot/two-agent-report.md`：两 Agent AgentSight 观测与统一化试跑；
- `my_paper_coding/failure_pilot/fault-matrix-report.md`：三类故障各 3 次的合成 pilot；
- `my_paper_coding/evaluation_gate/gate-report.md`：三任务跨任务归因与反事实验证门；
- `my_paper_coding/failure_pilot/results/real-pilot-inventory-20260928-r2/`：真实 AgentSight pilot 的 session、统一 trace、归因和反事实审计；
- `my_paper/方向框架/01_跨层因果边归因与可验证诊断/05_归因方法文献对比与适配器方案.md`：参考论文方法对比与下一版 adapter 方案；
- `my_paper/进展/进展_v0.7_2026-09-28.md`：当前进展、成本闸门和研究闸门。

## Go / No-Go

- Go：30–50 条带真值失败 trace 上，完整证据相对消息日志基线在至少一个主指标上有稳定、可解释的提升。
- No-Go：提升仅来自更长文本输入、标签泄漏或同一个 LLM judge 的自洽偏差；此时转方向 02 或 05。

## 当前下一步

先完成 0 API 的 adapter 预检：从 AgentSight SQLite、raw stream、框架日志和任务验证器自动生成带 provenance 的统一事件，移除对固定 `ground_truth.json` 生成 trace 的依赖。预算重新明确后，再运行错误传播和路由/角色错误 pilot；只有三类 pilot 都通过观测、独立真值和反事实检查，才扩展到每类至少 10 次，最终累计 30–50 条真实失败 trace。
