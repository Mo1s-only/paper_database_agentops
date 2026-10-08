# AgentSight 官方能力与论文创新空白

更新时间：2026-09-29

## 1. 官方来源

- [Eunomia AgentSight 总览](https://eunomia.dev/zh/agentsight/)
- [Eunomia 中文主页](https://eunomia.dev/zh/)
- [阿里云 AgentSight 使用文档](https://help.aliyun.com/zh/alinux/how-to-use-agentsight)

以下判断只针对上述官方页面明确写出的能力。页面没有说明的功能统一记为“官方未声明”，不直接等同于“实现中不存在”。

## 2. 官方已经覆盖的能力

| 能力 | 官方说明 | 对本课题的含义 |
|---|---|---|
| 零侵入系统观测 | 通过 eBPF、SSL/TLS 流量拦截、进程监控和文件/网络事件观测 Agent | 不能把“使用 eBPF 观测 Agent”作为独立创新 |
| LLM 与系统行为关联 | 关联 LLM 流量、进程执行、文件访问和系统活动 | 不能把“跨 LLM/进程/文件关联”单独作为创新 |
| Token 与成本分析 | 按 Agent、任务、角色和单次 LLM 调用分析 Token，支持缓存 Token | 你的成本审计应把 AgentSight 作为已有能力基线 |
| 审计与会话查询 | LLM 调用、提供商、模型、命令行参数、进程行为和筛选统计 | 不能把“记录原始审计事件”写成新贡献 |
| 会话中断诊断 | 覆盖限流、鉴权、流式截断、上下文超限、崩溃、重试风暴、死循环等 18 类中断 | 你的故障分类必须超出已有中断标签，或证明任务级责任标签提供额外价值 |
| 轨迹格式 | 支持 ATIF v1.7 入库、导出、离线分析、回放和评测 | 不能把“导出标准 trace”本身作为核心创新 |
| 资源与拓扑 | CPU、RSS、进程树、工具调用、文件活动、网络活动和子 Agent 拓扑 | 需要研究这些证据如何改变 Agent/Step/Edge 归因，而非重新展示它们 |
| 因果归因 | 阿里云文档明确写有“基于可复核证据辅助定位轨迹中的失败根因”；证据不足时返回“无法判断” | 必须先审计其实际输出，再决定你的方法是扩展、复现还是改进，不能声称 AgentSight 没有归因能力 |
| 安全审计保护 | 可配置保护目录和敏感文件，记录凭据外发风险；当前文档说明为审计模式，不阻断 Agent | 不应把运行时安全阻断作为你的空白，Eunomia 的 ActPlane 已覆盖策略控制方向 |
| 多 Agent/多框架发现 | 官方列出 OpenClaw、Copilot Shell、Claude Code、Codex CLI、QwenCode、Hermes、AgentScope，并支持自定义匹配 | “支持第二个框架”是必要评测，不是单独论文创新 |
| OpenTelemetry | 可导出 GenAI `gen_ai.*` span，且无需进程内插桩 | 你的 Adapter 应兼容 OTel/ATIF，同时补充任务判据和责任证据 |

## 3. 不应再使用的论文主张

以下主张已经被官方能力覆盖，不能直接作为论文贡献：

1. 提出一种零侵入 eBPF Agent 观测工具。
2. 捕获 LLM 调用、Token、进程、文件、网络和资源事件。
3. 将 LLM 流量与系统行为关联。
4. 对 Agent 会话进行审计、可视化和成本统计。
5. 输出标准化 Agent trace 或 OpenTelemetry span。
6. 发现重试风暴、死循环、上下文超限和其他会话中断。
7. 泛化支持多个 Agent 类型。

## 4. 仍可能形成论文贡献的方向

### 4.1 任务级决定性责任协议（最强候选）

AgentSight 官方文档只说明“基于可复核证据辅助定位失败根因”，没有在页面上给出 Agent/Step/Edge 的公开定义、独立任务 oracle、干预协议、无关控制和跨任务准确率。因此可研究：

```text
失败任务 + 原始系统观测 + 应用日志 + 独立任务判据
    → Agent/Step/Edge 候选
    → 最小修复干预
    → 责任确认、拒答或多根因输出
```

这不是声称 AgentSight 没有因果归因，而是把产品级“根因辅助定位”转化为可复现、可评测的责任定义。

### 4.2 带 provenance 的跨层 Trace Adapter

AgentSight 已经能产生 ATIF/OTel 和系统事件，但你的 Adapter 可以研究更严格的证据对齐：

- 从 SQLite、raw stream、ATIF/OTel、框架日志和工具输出自动重建事件；
- 给每个字段记录原始记录 ID、来源、时间关系和推断置信度；
- 区分 `observed`、`inferred`、`validated` 和 `unknown`；
- 在 AgentSight 不理解应用语义时，用独立任务 validator 补充 Agent/Step/Edge 标签；
- 不读取固定 manifest 中的事件顺序来生成 trace。

Adapter 本身属于方法基础设施，必须通过归因效果或可审计性实验体现价值。

### 4.3 观测模态增益实验

核心不是“收集更多数据”，而是验证数据是否改变诊断结果：

```text
A：应用日志
B：AgentSight/eBPF
C：应用日志 + AgentSight/eBPF
```

在相同任务、故障和判据下比较 Agent、Step、Edge 的 Hit@k、MRR、反事实翻转率、误干预率、拒答率、对齐率和开销。只有 C 稳定优于 A，系统层观测才可能成为论文核心贡献。

### 4.4 多错误传播与责任不确定性

官方页面强调会话和中断诊断，但没有公开说明如何区分：

```text
上游触发错误 → 中间传播错误 → 下游表现错误
```

可以研究多根因、传播边、并行症状、责任置信度和拒答校准。输出不应强制给出一个根因。

### 4.5 归因后修复的下游效用

把归因结果接到最小修复、重试、隔离或人工复核，测量修复成功率、误干预率、人工诊断时间和成本。Eunomia 已有 ActPlane 的策略控制方向，因此你的重点应是“证据驱动的责任确认与修复选择”，而不是重新实现安全阻断。

## 5. 推荐的论文主线

> **AgentSight-compatible, provenance-aware, counterfactually validated failure attribution for multi-agent tasks**

中文可表述为：

> 面向多 Agent 任务失败的可审计跨层证据适配与反事实责任归因。

建议贡献结构：

1. 一个兼容 ATIF/OTel 和系统原始事件的跨层 Adapter；
2. 一个输出 Agent/Step/Edge、provenance、置信度和拒答的责任图模型；
3. 一个基于独立任务判据和最小干预的决定性责任协议；
4. 应用日志、eBPF、融合观测的模态消融和跨框架数据集。

## 6. 当前必须先验证的研究闸门

1. AgentSight 官方“因果归因”实际输出到什么粒度，是否有 Agent/Step/Edge 和证据链；
2. 现有输出是否使用任务 oracle，还是只做会话级异常解释；
3. Adapter 能否不读取固定 manifest 重建同一条 trace；
4. 融合观测相对应用日志是否有稳定增益；
5. 反事实修复是否在真实可重放环境中成立。

在这五项没有通过前，不应把项目表述为“提出了新的 AgentSight”，也不应声称已经完成通用因果定位。
