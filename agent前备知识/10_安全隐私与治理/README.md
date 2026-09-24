# 第 10 章：安全、隐私与治理

本章正文：[详细教程](详细教程.md)；学习后完成：[练习与验收](练习与验收.md)；最后对照：[练习与验收答案](练习与验收答案.md)。

## 本章定位

Agent 能读写文件、调用网络和操作外部系统；可观测平台又会集中收集 prompt、响应、路径、凭据和行为证据。安全不是附加章节，而是 AgentOps 的边界条件。

## 学习目标

- 理解提示注入、间接提示注入、工具越权和数据外泄。
- 理解最小权限、能力隔离、沙箱、审批和审计。
- 理解 trace 数据中的秘密、个人信息、业务数据和模型输入风险。
- 理解供应链、Skill/Plugin/MCP server 的信任问题。
- 为数据采集定义保留、脱敏、访问控制和删除策略。

## 威胁面

| 面 | 典型风险 | 控制 |
|---|---|---|
| 输入 | 恶意网页/文档中的间接注入 | 来源标记、内容隔离、策略检查 |
| 模型 | 指令混淆、敏感信息泄露 | 上下文最小化、输出过滤 |
| 工具 | 越权、破坏性副作用 | allowlist、沙箱、审批、幂等 |
| 多 Agent | 污染消息被高信任转发 | 来源与置信度、独立验证 |
| MCP/Plugin | 恶意或被篡改服务 | 签名、权限声明、版本锁定 |
| Trace | 密钥、Prompt、路径、响应泄露 | 脱敏、加密、访问控制、保留期限 |

## 观测与安全的张力

记录越多，诊断可能越强，但隐私、存储和攻击面也越大。应以“诊断所需最小证据”为原则，敏感原始载荷与派生特征分离，并记录 redaction 与 completeness。

## 项目内材料

- [Agent 安全与治理](../../lab/agentsight/docs/design/market/03-agent-security-and-governance.md)
- [提示注入案例](../../lab/agentsight/docs/experiment/case-study/prompt-injection-detection/README.md)
- [MCP/Skill/Plugin 验证](../../lab/agentsight/docs/design/market/04-mcp-skill-plugin-verification.md)
- [AgentSight 快速复现](../../lab/agentsight/快速复现AgentSight.md)
- [AgentSight 输出数据说明](../../lab/agentsight/results/AgentSight输出数据说明.md)

## 本章完成标准

能为一条 Agent trace 完成数据分类和威胁建模，并给出最小采集、脱敏、保留、访问与审计策略。
