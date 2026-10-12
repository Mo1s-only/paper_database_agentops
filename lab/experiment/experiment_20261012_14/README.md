# experiment_20261012_14｜SSE 原始时钟持久化与协议 v0.2 真实验证

## 目标

使用修复后的本地 AgentSight release 二进制运行一次真实 Claude Code CLI 会话，验证完整链路：

1. 纳秒级 boot epoch 换算使进程启动时间直接落入应用 Popen 边界；
2. 时间归一化器写入的 `_agentsight_clock` 能穿过 SSE 聚合器；
3. `tool_calls` 保存原始 boot-relative 时间、boot epoch 锚点和锚点不确定度；
4. 应用事件协议 v0.2 能生成并严格校验一条六事件真实生命周期。

## 调用前固定证据

- AgentSight 版本：1.0.31。
- release 二进制 SHA256：`6ef1946310895168c5df6b57addf8622725d45dc579c6a91e0fe441812d4211c`。
- Python：57 项测试通过。
- AgentSight analysis：128 项测试和 2 项文档测试通过。
- AgentSight 核心时钟：4 项测试通过。

## 预算

本实验只允许 1 个真实 CLI 会话，单会话上限 0.10 USD，不自动重试。实验前累计 CLI 报告费用为 1.626016 USD，计划最坏累计值为 1.726016 USD，低于 2.00 USD 硬停止线。

## 实验结果

- `VERIFIED`：真实会话一次成功，费用 0.024832 USD；原生 init/tool_use/tool_result/result 均为 1，工具生命周期闭合，AgentSight 共享 tool_call ID 唯一命中。
- `VERIFIED`：进程启动时间 1791785496876 ms 落在应用 Popen 区间 1791785496874.819–1791785496876.4282 ms 内，追加时钟校正为 0。
- `VERIFIED`：SSE 工具行已保存原始 boot 时间 `154499649757 ns`、boot epoch `1791785365750464700 ns` 与锚点字段，epoch 公式复算一致。
- `VERIFIED`：协议 v0.2 生成 6 条事件、1 个闭合 session，并通过独立严格读取校验；事件文件 SHA256 为 `f9fb7a628866c127f27749d95b582e4697cd3ce133f7eade7a16aa572a5c47b0`。
- `INFERRED`：应用 PID 81 与观测器 PID 1758 的关系由同一 session、启动区间、进程名和共享工具 ID 支持，尚无通用 PID 数字换算。
- `UNVERIFIED`：记录中的锚点 bracket 为 0 ns，只说明这一次配对采样的整数读数未显示宽度；它没有计入计时器分辨率，不能解释为真实误差为零。

## 成本审计

调用前的 1.626016 USD 来自旧范围台账。实验后扩大扫描范围并按 provider session ID 去重，发现旧台账漏计 4 个历史唯一会话，共 0.5328595 USD；另发现 1 份重复日志并只计一次。去重后的全仓累计费用为 2.183708 USD，其中本次实验为 0.024832 USD。由于已经超过 2.00 USD 硬停止线，后续停止真实 API 调用，只使用现有数据做离线回放与分析。

## API 调用前证据状态

- `VERIFIED`：实验目录、验收条件、预算、源码测试和二进制哈希均已在调用前固定。
- 调用前 `UNVERIFIED` 的“SSE 原始时钟写入 SQLite”和“协议 v0.2 真实闭环”已在本次实验升级为 `VERIFIED`。

原始日志、SQLite 和事件 JSONL 写入 `results/`；该目录受仓库 `.gitignore` 保护。可提交目录只保存计划、摘要、报告和必要哈希。
