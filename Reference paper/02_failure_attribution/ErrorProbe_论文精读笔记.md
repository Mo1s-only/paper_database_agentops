# ErrorProbe 论文精读笔记

## 论文信息

- 标题：Towards Self-Improving Error Diagnosis in Multi-Agent Systems
- 作者：Jiazheng Li、Emine Yilmaz、Bei Chen、Thu Le
- Venue/年份：Findings of ACL 2026
- 官方来源：[ACL Anthology](https://aclanthology.org/2026.findings-acl.98/)
- 本地论文：`ErrorProbe_Self_Improving_Error_Diagnosis_ACL2026.pdf`
- 阅读目的：反向追踪、工具验证、跨域记忆和自动归因
- 状态：精读；发表状态 `VERIFIED`

## 1. One-sentence contribution

ErrorProbe 将失败分类、症状驱动的 backward tracing、专门的诊断 Agent 团队和经过执行验证的 episodic memory 结合，用于 Agent/Step 级故障归因。

## 2. Problem setting

输入是多 Agent 交互轨迹和失败症状，输出是负责 Agent 及最早的错误诱发步骤。论文关注长轨迹、延迟表现和跨 Agent 依赖造成的定位困难。

## 3. Method core

第一阶段将 MAST taxonomy 操作化为轻量异常检测器；第二阶段从最终症状向后检索可能相关的历史步骤；第三阶段由 Strategist、Investigator、Arbiter 生成和验证假设。只有经过代码沙箱或工具执行确认的错误模式才能写入 verified episodic memory，从而避免错误记忆污染。

## 4. Evidence

论文在 TracerTraj、Who&When-Algo 和 Who&When-Hand 上比较 LLM-as-a-Judge、无记忆 ErrorProbe 和带记忆 ErrorProbe。摘要报告其在 Step-level 定位上明显优于基线；消融显示 backward tracing、结构化失败信号和 verified memory 各有增益。论文还报告跨域迁移和多模型实验。

## 5. Limitations

它仍以交互文本和工具验证为主要输入，没有系统级 syscall、进程谱系或网络事件。验证依赖可执行环境和额外 Agent 调用，成本可能随候选数增长。其“verified memory”解决的是诊断模式复用，不是跨框架原始观测对齐。

## 6. Use for my thesis

ErrorProbe 是你的 backward candidate search 和反事实验证的重要近邻。你的工作必须把“跨层观测适配”作为前置层，并比较没有 eBPF、只有应用日志和融合观测的效果。不能把“反向搜索+执行验证”单独宣称为新方法。

## 7. Claim–evidence rows

| Claim | Evidence | Status |
|---|---|---|
| 症状驱动的反向检索可缩短长轨迹诊断上下文 | 方法第 4 节、消融实验 | `VERIFIED` |
| 执行验证可约束诊断记忆写入 | verified episodic memory 机制 | `VERIFIED` |
| 它解决了 eBPF 与应用日志的跨层对齐 | 论文输入不包含该问题 | `UNVERIFIED` |
