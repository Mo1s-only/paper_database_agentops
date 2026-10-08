# ReLog 论文精读笔记

## 论文信息

- 标题：ReLog: Execution-Aware Logging with Runtime Feedback for LLM-Oriented Debugging
- 作者：Xin Wang 等
- Venue/年份：ASE 2026 Research Papers；arXiv 版本为 2026
- 来源：[arXiv](https://arxiv.org/abs/2603.29122v2)；ASE 2026 页面列出该论文
- 本地论文：`ReLog_Execution_Aware_Logging_LLM_Debugging.pdf`
- 阅读目的：日志质量、运行时反馈和下游调试效用
- 状态：精读；arXiv/会议节目状态需以最终出版记录为准，标记 `VERIFIED` 为论文存在，正式版本细节 `INFERRED`

## 1. One-sentence contribution

ReLog 用“生成—执行—评价—修正”的运行时反馈循环生成更适合 LLM 调试的日志，并以缺陷定位和修复效果而非日志文本相似度评价日志质量。

## 2. Problem setting

传统自动日志生成通常静态分析一次生成，并以接近开发者日志作为评价标准。但 LLM 消费日志时，文本相似并不意味着能支持定位或修复。ReLog 将日志质量定义为对下游调试任务的实际帮助。

## 3. Method core

系统让 LLM 生成日志语句，在程序运行后检查日志是否支持缺陷定位和修复，再根据反馈迭代生成。实验覆盖直接调试和源代码不可用的间接调试，强调运行时上下文和任务导向日志。

## 4. Evidence

- 基于 Defects4J 构建日志和调试基准。
- 直接调试设置报告 F1=0.520，并修复 97 个缺陷。
- 间接调试设置最佳 F1=0.408。
- 多 LLM 实验和编译修复、迭代反馈消融用于验证方法机制。

证据位置：摘要、§2 Problem、§3 Method、§4 Benchmark、§5 Results、§Ablation。

## 5. Limitations

ReLog 面向传统软件缺陷和源代码/日志生成，不处理 Agent 角色、消息依赖或系统边界事件。日志生成需要改动程序并进行多轮执行，和你的零侵入 eBPF 观测目标不同。

## 6. Use for my thesis

ReLog 提醒你不能只报告日志“看起来更完整”，而应证明日志对 Agent/Step/Edge 归因和反事实验证的下游效用。可以把“应用日志质量”定义为模态消融中的一项实验变量，并报告对齐率、定位准确率和诊断成本。

## 7. Claim–evidence rows

| Claim | Evidence | Status |
|---|---|---|
| 日志应按下游调试效用评价 | 摘要、Defects4J 评测 | `VERIFIED` |
| 运行时反馈可改进日志质量 | 迭代生成与消融 | `VERIFIED` |
| 生成更好的应用日志即可解决跨层 Agent 归因 | 论文未研究 eBPF/Agent responsibility | `UNVERIFIED` |
