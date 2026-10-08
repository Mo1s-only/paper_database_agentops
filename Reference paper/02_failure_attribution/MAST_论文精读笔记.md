# MAST 论文精读笔记

## 论文信息

- 标题：Why Do Multi-Agent LLM Systems Fail?
- 作者：Mert Cemri 等
- Venue/年份：NeurIPS 2025 Datasets and Benchmarks Track
- 官方来源：[NeurIPS Proceedings](https://papers.nips.cc/paper_files/paper/2025/hash/b1041e52d3be19f0a9bc491657488e4a-Abstract-Datasets_and_Benchmarks_Track.html)
- 本地论文：`MAST_Why_Do_Multi_Agent_LLM_Systems_Fail.pdf`
- 阅读目的：失败分类、跨框架数据集和独立标注
- 状态：精读；发表状态 `VERIFIED`

## 1. One-sentence contribution

MAST 建立了多 Agent 系统失败分类法和 MAST-Data 数据集，用跨框架、人工标注的失败轨迹描述多 Agent 失败的结构性来源。

## 2. Problem setting

论文不直接定位单个责任步骤，而是问多 Agent 系统为什么失败。作者分析五个流行框架、150 多个任务和 1600 多条轨迹，将失败组织为 specification/system design、inter-agent misalignment、task verification/termination 三个大类，共 14 个细粒度失败模式。

## 3. Method core

作者先从失败轨迹中迭代构造 taxonomy，再由专家进行人工分析并用 LLM annotator 扩展到大规模数据。分类不是简单按最终答案错误，而是观察角色规范、信息交接、验证和终止过程。论文还比较角色规范和编排策略等干预方式，说明许多失败不能靠简单提示修复。

## 4. Evidence

- 7 个 Agent 框架，1600+ 条带标注轨迹。
- 150 条轨迹用于专家驱动 taxonomy 构造。
- 三位专家参与主要分析，报告 Cohen's kappa = 0.88。
- 14 类失败模式覆盖系统设计、Agent 对齐和任务验证。
- 发布 MAST-Data、taxonomy 和 LLM annotator。

证据位置：摘要、§3 Taxonomy、§4 Dataset、§5 Analysis 和 NeurIPS 官方摘要。

## 5. Limitations

MAST 的主要产物是失败分类和统计分布，不是逐条的因果责任边。LLM annotator 不能直接视为绝对真值；分类标签可能受到框架、任务和标注协议影响。论文也不能替代工具级或系统级 RCA。

## 6. Use for my thesis

MAST 可用于定义故障注入矩阵和独立标签体系。我的 Adapter 应把 MAST 的语义类别作为 validator 或候选特征，而不能把它当成系统观测结果。特别应把“错误传播”和“任务验证缺失”拆开，以免把最终症状错误地标为工具根因。

## 7. Claim–evidence rows

| Claim | Evidence | Status |
|---|---|---|
| 多 Agent 失败具有结构化类别 | MAST taxonomy、14 modes | `VERIFIED` |
| taxonomy 可跨多个框架使用 | 7 frameworks 的 MAST-Data | `VERIFIED` |
| MAST 可直接提供决定性 Edge 真值 | 论文主要提供类别标签 | `UNVERIFIED` |
