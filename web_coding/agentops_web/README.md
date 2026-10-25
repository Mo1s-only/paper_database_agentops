# AgentOps Web

面向 AgentOps / 多智能体系统的可扩展 Web 观测控制台。当前版本使用本机 SQLite 保存工作区数据，并保留带来源标记的确定性示例，覆盖“总览 → Trace 检索/快速检查 → Span 回放 → 项目/告警 → MCP/SDK 接入 → 部署原型”的核心闭环。

## 技术选择

- **Next.js 16.4 + React 19 + TypeScript**：沿用参考项目的 Next.js 技术方向，并采用当前 Active LTS 的安全修复版本。
- **同源 Route Handler**：浏览器不直接持有后端密钥；未来可接 FastAPI、ClickHouse 或鉴权网关。
- **无 UI 框架依赖的设计系统**：降低首屏体积并便于论文项目定制。
- **standalone Docker 输出**：可以部署到单机 Docker，后续再扩展到容器平台。

参考依据和未实现边界见 [PROVENANCE.md](./PROVENANCE.md)。
后续结合论文研究的接口边界与验证门见 [RESEARCH_EXTENSION.md](./RESEARCH_EXTENSION.md)。
启动方式、五分钟体验路线和功能边界见 [使用指南.md](./使用指南.md)。

## 产品化改进（2026-10-24）

- 总览、Metrics、Traces 使用真实时间窗口过滤；刷新重新请求数据；移除无依据的环比数字。
- 搜索视图和收藏保存在浏览器；项目、告警策略、人工标签和导入 Trace 保存在服务端 SQLite，并检查并发编辑版本。
- 全局来源状态、数据连接检查、键盘可访问对话框、加载骨架、异常恢复与 404。
- 远程请求 8 秒超时、不跟随重定向；Trace 结构校验拒绝缺失父节点和循环引用。
- `/api/health` 提供读取链路健康检查；安全响应头与 Docker 构建上下文隔离。
- 这是商业化方向的本地产品基础，尚未包含 SaaS 身份、租户、计费、真实采集服务与通知投递。

## 已实现

2026-10-25 补充：新增 SQLite 单机持久化、Trace JSON 事务导入、来源筛选、版本冲突检测与本机操作记录。运行环境要求 Node.js 24+。写入只面向本机同源页面，不能替代登录鉴权；详见使用指南。

- 响应式深色/浅色控制台、项目切换、全局命令搜索
- 总览：Trace、Span、Token、成本、错误率、吞吐趋势、模型用量
- Metrics：P95 延迟、错误率、Span 调用类型、Trace 延迟排行、模型成本明细
- Trace 列表：调用分类统计、搜索、状态筛选、排序、收藏、分页、JSON 导出、右侧快速详情
- Trace 详情：调用树、瀑布时间线、Span 输入/输出/原始数据、错误定位
- 失败归因原型：透明规则基线、首要可疑 Span、传播路径、候选证据排行，并明确标记为 `UNVERIFIED`
- Ground Truth 标注：人工选择根因 Span、失败类型和证据说明，本地保存并导出版本化 JSON
- 评测工作台：聚合失败 Trace、规则基线候选与人工标签，按已标注样本计算一致率并导出评测集
- 通知中心：失败 Trace、延迟阈值演示通知与告警策略入口
- 项目管理交互、告警阈值与启停交互
- MCP Server 客户端配置生成、工具能力目录
- Agent Hosting 部署流程原型、浏览器内状态模拟、运行详情、资源状态、构建信息和日志抽屉
- API Key 列表与一次性演示密钥交互（不会生成真实凭据）
- Python、TypeScript、OpenTelemetry 接入片段
- `/api/v1/*` API 边界、mock/remote 数据模式、Dockerfile、指标单元测试

## 本地运行

```powershell
pnpm install
pnpm dev
```

访问 <http://localhost:3000>。生产构建：

```powershell
pnpm typecheck
pnpm test
pnpm build
pnpm start
```

## 接入真实后端

复制 `.env.example` 为 `.env.local`，设置：

```dotenv
AGENTOPS_DATA_MODE=remote
AGENTOPS_API_URL=https://your-api.example.com
AGENTOPS_API_TOKEN=server-side-token
```

远端需要提供：

- `GET /v1/projects`
- `GET /v1/traces`
- `GET /v1/traces/:id`
- `GET /v1/metrics/overview`
- `GET /v1/alerts`

当前 `lib/data-source.ts` 是替换数据层的唯一入口。正式上线时建议在 FastAPI 层完成租户隔离、分页、时间范围过滤与 RBAC；ClickHouse 负责高吞吐 Trace/Span 聚合，PostgreSQL/Supabase 负责项目、成员和告警规则。

MCP 与部署页面当前是前端流程原型；设置页已移除无实际鉴权作用的演示密钥生成器。上线时应分别接入受鉴权的 MCP 服务、部署控制面和密钥管理服务；浏览器只接收掩码或一次性返回值。

## 数据真实性

`lib/mock-data.ts` 只用于可复现的 UI 演示，不代表真实实验结果。论文使用前应接入实验日志，并在实验报告中保存导出时间、数据版本与查询条件。
