# 参考来源与实现边界

## VERIFIED

- 上游仓库：<https://github.com/AgentOps-AI/agentops>
- 调研版本：`f8e907b92dabe47232978023fdcb01e2a7d4b752`
- 上游 `app/README.md` 明确给出 Next.js Dashboard、FastAPI API、ClickHouse 追踪分析、Supabase 身份/业务数据的分层。
- 上游 Dashboard 的核心页面包括 Overview、Traces、Projects、Time Travel、Deploy 和 Settings；其 Trace 表格展示状态、耗时、成本、Span、错误、标签，并提供详情下钻。
- 上游源码的 Trace drilldown drawer 会聚合成本、Token、LLM 调用、工具调用与错误信息，并提供调用树和完整详情入口；本项目据此加入了快速详情抽屉和调用分类摘要。
- `https://app.agentops.ai/traces` 的公开页面信息显示 Projects、Traces、Metrics、MCP、Deploy、API Keys 等导航入口。
- 上游仓库根目录 `LICENSE` 是 MIT，但 `app/LICENSE` 单独采用 Elastic License 2.0，并限制把该软件的大部分功能作为托管/管理服务提供给第三方；本项目因此采用独立实现，不复制 `app/` 源文件。

## INFERRED

- 本项目选择 Next.js + TypeScript，是因为现有上游同样采用 Next.js，而且前端类型、同源 API 边界、容器化部署与后续多人协作都较成熟。没有照搬上游的 Next.js 15.2.3：该版本已被官方标为存在安全漏洞，项目改用 2026-10-19 可用的 Next.js 16.4.2。
- Trace 回放采用“列表快速抽屉 + 独立详情页瀑布时间线”的双层结构，用于兼顾高频排查和完整故障复盘。
- MCP、Deploy 与 API Keys 采用前端适配器边界，是为了保留未来接真实服务的交互契约，同时不在论文演示阶段引入不可审计的外部副作用。
- 失败归因视图使用本项目独立实现的透明规则基线，只用于验证研究数据契约与 UI 工作流；页面明确显示方法版本和 `UNVERIFIED` 状态。

## UNVERIFIED / NOT IMPLEMENTED

- 未连接真实 AgentOps Cloud、ClickHouse、Supabase、Stripe 或通知服务。
- 告警策略、新建项目、部署和 API Key 目前是交互原型；页面会明确提示演示模式，不把它们当作持久化结果。
- 2026-10-20 浏览器核对时，在线 `/traces` 经 Google OAuth 跳转到未登录账号输入页；由于当前内置浏览器没有可复用的已登录 Google 会话，登录后 SaaS 界面仍属 `UNVERIFIED`。实现细节以固定提交的开源源码为准。
- 没有声称与上游私有部署或在线 SaaS 的全部功能一一等价。

## 下一研究验证门

用论文实验产生的真实 Trace JSON 替换 `lib/mock-data.ts`，确认字段映射能表达多智能体 handoff、tool call、LLM call、错误传播与因果归属。
