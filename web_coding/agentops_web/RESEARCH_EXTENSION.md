# 研究功能扩展边界

本项目只仿照 AgentOps 的产品信息架构与观测工作流，代码和接口为独立实现。以下是后续结合“多智能体系统监控、Tracing 与失败归因”研究方向时建议保持稳定的边界。

## VERIFIED：当前已有基础

- `Trace` / `Span` 已表达父子关系、agent、模型、工具、输入输出、耗时、Token、成本、状态与错误。
- `lib/data-source.ts` 是演示数据与远端后端之间的单一切换入口。
- `/api/v1/*` Route Handler 隔离浏览器与后端密钥。
- Trace 详情已有调用树、时间瀑布和 Span 检查器，可作为归因结果的可视化载体。
- `lib/attribution.ts` 已实现一个可解释、可测试的规则基线；错误 Trace 页面会展示可疑 Span、传播路径和证据排行，并明确标记为 `UNVERIFIED`。
- 错误 Trace 支持人工 Ground Truth 标注和版本化 JSON 导出；未标注前显示 `AUTHOR_INPUT_NEEDED`，保存后才显示 `VERIFIED HUMAN LABEL`。
- `/evaluations` 已将失败 Trace、规则基线候选和人工标签组织成可导出的对照集；只对已有人工标签的样本计算一致率，缺少标签时明确显示“待标注”。

## INFERRED：推荐研究扩展

当前规则基线位于独立模块而不是 React 组件中。正式研究阶段建议替换为独立分析服务，并继续通过版本化结果接入：

```ts
interface FailureAttribution {
  traceId: string;
  method: string;
  methodVersion: string;
  rootSpanId: string | null;
  confidence: number | null;
  evidence: Array<{
    spanId: string;
    signal: 'error' | 'latency' | 'tool' | 'handoff' | 'semantic';
    observation: string;
    score: number | null;
  }>;
  generatedAt: string;
}
```

建议的数据路径：采集 SDK / OpenTelemetry → 原始 Trace 存储 → 信号抽取 → 多信号关联 → 失败归因 → 版本化结果 API → Trace 详情页。

UI 后续可在完整 Trace 回放中加入三个研究视图：

1. 故障传播路径：在调用树上高亮从触发点到最终失败的传播链。
2. 证据面板：把日志、延迟、工具失败、handoff 异常和语义信号与具体 Span 对齐。
3. 方法对比：展示规则法、统计法或语义分析法的结果、置信度和分歧，不把推断伪装成事实。

## UNVERIFIED / AUTHOR_INPUT_NEEDED

- 论文最终采用的归因问题定义、算法与评价指标尚未确定。
- 真实实验 Trace 的字段、采样方式、双人/盲评 Ground Truth 标注流程尚未接入；当前单人本地标注只验证数据结构与交互。
- 当前演示数据不能用于报告算法准确率、召回率或性能结论。
- 评测页的一致率是浏览器本地标签上的派生值，只用于验证评测管线，不是论文实验结果。

## 下一研究验证门

先准备一小批带人工标注的真实失败 Trace，至少覆盖工具超时、LLM 输出异常、agent handoff 丢失和上游错误传播；再据此冻结 `FailureAttribution` 字段与 Ground Truth 规则。字段稳定后，前端可直接新增归因层而无需重写现有观测页面。
