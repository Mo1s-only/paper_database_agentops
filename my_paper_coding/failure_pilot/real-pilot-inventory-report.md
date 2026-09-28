# 真实 inventory-silent-tool Pilot 报告

**版本**：v0.1
**时间**：2026-09-28
**状态**：`VERIFIED_FOR_THIS_CONTROLLED_REAL_AGENT_RUN`

## 运行过程

第一次尝试因 WSL DNS 失效返回 `EAI_AGAIN`，AgentSight 记录 `0 API calls · 0 tokens`，没有产生模型费用；该运行已保留在 `results/real-pilot-inventory-20260928/`。

修复 DNS 并加入 90 秒单调用超时后，第二次运行成功完成 Agent A/B 两次调用，结果目录为 `results/real-pilot-inventory-20260928-r2/`。

## 真实结果

| 项目 | 结果 |
|---|---:|
| Agent A 退出码 | 0 |
| Agent B 退出码 | 0 |
| API 调用结果数 | 2 |
| 实际成本 | 0.218846 USD |
| `process_nodes` | 53 |
| `audit_events` | 123 |
| `llm_calls` | 6 |
| `tool_calls` | 4 |
| `network_targets` | 4 |
| 统一 trace 事件 | 7 |

Agent A 写入 `route.json`；Agent B 读取路由、调用 `fake_inventory.py alpha`，得到 `available=0`，再写入 `decision.json` 并判定任务不满足 `available=1`。

## 归因结果

归一化分析器定位到：

- 责任 Agent：`agent_b`；
- 责任 Step：`agent_b.bash_tool_call`；
- 责任 Edge：`evt-004 → evt-005`；
- 证据区间召回：`1.0`。

## 反事实结果

离线重放把责任工具结果从 `available=0` 改为任务要求的 `available=1`：

- 原始任务：失败；
- 修复责任事件后：成功；
- 修改无关元数据后：仍失败。

这验证的是任务判据层的反事实协议，不是再次调用 Claude 的真实重放。

## 证据边界

- **VERIFIED**：真实 API 调用、AgentSight 观测、统一 trace、责任标签和离线反事实重放均完成；
- **UNVERIFIED**：错误传播、路由/角色错误的真实 AgentSight 运行；跨任务泛化；统计显著性；
- **限制**：责任真值仍来自受控故障 manifest，样本只有 1 条真实任务，不能作为论文最终准确率。
