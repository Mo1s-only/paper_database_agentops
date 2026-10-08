# GALA 论文精读笔记

## 论文信息

- 标题：GALA: Graph-Augmented LLM Agents for Root Cause Analysis and Incident Response in Microservices
- 作者：Yifang Tian 等
- Venue/年份：ASE 2026 Research Papers；当前同时有 arXiv 预印本
- 官方来源：[ASE 2026](https://conf.researchr.org/details/ase-2026/ase-2026-research-track/5/GALA-Graph-Augmented-LLM-Agents-for-Root-Cause-Analysis-and-Incident-Response-in-Mic)
- 本地论文：`GALA_Graph_Augmented_LLM_RCA_Microservices_ASE2026.pdf`
- 阅读目的：异构 telemetry、依赖图和 RCA 评估
- 状态：精读；会议状态 `VERIFIED`

## 1. One-sentence contribution

GALA 用服务依赖图限制 LLM 调查范围，以 trace 和图结构感知的 STRIX 模块生成候选，并结合多模态证据输出根因、事件摘要和处置建议。

## 2. Problem setting

论文研究复杂微服务事故：trace、日志、指标等遥测信号分散在服务依赖图上，单一 telemetry 容易遗漏关系，LLM 自由探索又可能产生幻觉。目标不仅是排序根因，还包括可操作的 incident response。

## 3. Method core

GALA 先利用服务依赖图约束探索范围，再使用 STRIX 进行 trace/graph-aware 候选评分，最后由 LLM 结合局部多模态证据生成诊断和行动建议。它还提出 SURE-score，将 RCA 输出质量交给有经验的 SRE 做结构化评价。

## 4. Evidence

ASE 官方摘要报告其在两个微服务基准上评估，并以 AC@1、SURE-score 和独立 SRE 评价对比 LLM baseline；官方页面称 AC@1 超过最佳 LLM baseline 25 个百分点以上。具体数据集、故障注入和统计细节应以论文正文/预印本为准。

## 5. Limitations

对象是微服务，不是 Agent 任务或自然语言消息责任。服务依赖图通常是较稳定的架构先验，而 Agent 的角色、消息和工具边会动态变化。RCA 输出质量也包含人类评分，不能直接替代反事实责任真值。

## 6. Use for my thesis

GALA 说明“多模态 telemetry + 依赖图 + LLM RCA”已经是相邻领域的竞争路线。你的差异应放在 Agent-specific graph：message/data/process/resource 边、任务 oracle、可拒答 provenance 和反事实干预，而不是单纯把多个信号喂给 LLM。

## 7. Claim–evidence rows

| Claim | Evidence | Status |
|---|---|---|
| 图结构可以限制 RCA 的搜索空间 | 官方摘要、STRIX 方法 | `VERIFIED` |
| 多模态 telemetry 可提升 RCA | 两个微服务基准的官方摘要结果 | `VERIFIED` |
| 微服务依赖图可直接代表 Agent 责任图 | 对象和语义不同 | `UNVERIFIED` |
