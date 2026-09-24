# 第 4 章：工具调用与 Agent 协议

本章正文：[详细教程](详细教程.md)；学习后完成：[练习与验收](练习与验收.md)；最后对照：[练习与验收答案](练习与验收答案.md)。

## 本章定位

工具把模型输出转化为真实世界副作用，也是 Agent 最常见的故障和安全边界。MCP、Skill 和 Plugin 属于能力暴露与组织机制，不能与 Agent 的推理或控制策略混为一谈。

## 学习目标

- 理解工具 schema、参数校验、返回值、错误码和超时。
- 理解同步/异步、流式、重试、幂等、取消和补偿操作。
- 理解 MCP 的 client、server、transport、tool/resource/prompt 等角色。
- 区分 Tool、Function Calling、MCP、Skill、Plugin 和 Agent。
- 为工具调用设计权限、审计、沙箱与副作用验证。

## 工具契约的最小字段

| 类别 | 字段 |
|---|---|
| 身份 | tool_name、version、provider |
| 关联 | run_id、agent_id、step_id、call_id、parent_id |
| 输入 | arguments、schema_version、input_hash |
| 执行 | start/end、timeout、retry、host/process |
| 输出 | result、status、error_type、output_hash |
| 副作用 | file/network/database/external_action |
| 安全 | principal、permission、approval、redaction |

## 关键故障

- 模型选错工具或参数；
- schema 验证失败；
- 工具返回显式错误；
- 工具返回“成功”但内容错误，即静默错误；
- 超时后重试造成重复副作用；
- 权限过大或路径/网络目标越界；
- 工具结果被错误解析、截断或归给错误步骤。

## 项目内材料

- [MCP 设计](../../lab/agentsight/docs/design/mcp/DESIGN.md)
- [MCP 测试夹具](../../lab/agentsight/docs/experiment/mcp-test/README.md)
- [MCP、Skill、Plugin 验证](../../lab/agentsight/docs/design/market/04-mcp-skill-plugin-verification.md)
- `Reference paper/03_diagnosis_localization/Tools_Fail_Detecting_Silent_Errors_in_Faulty_Tools_EMNLP2024.pdf`
- [AgentSight 输出数据说明](../../lab/agentsight/results/AgentSight输出数据说明.md)

## 本章完成标准

能为一个具有文件或网络副作用的工具写出完整契约、错误模型、权限边界与审计事件，并说明如何验证声明的结果真的发生。
