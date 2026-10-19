# 公开归因数据统一协议兼容性报告

运行时间：2026-10-16T08:28:58.693795+00:00  
协议：`attribution-benchmark-record-v0.1`

## 汇总

| 数据集 | 记录 | Schema有效 | Run覆盖 | Agent覆盖 | Step/span覆盖 | Relation覆盖 | 关系重建率 | 证据完整率 | 真值拒绝率 | 警告 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Who&When | 184 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | 40.00% | 0 |
| TRAIL | 148 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | 80.54% | 3 |
| AgentTrace | 550 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | 0.00% | 1 |

总计处理 **882** 条记录；schema 有效率 **100.00%**，关系重建率 **100.00%**，证据完整率 **100.00%**，五类真值槽位拒绝率 **21.86%**。

拒绝率表示源数据没有提供相应粒度真值，是诚实保留的数据边界，不是适配器失败率。

## 五类真值覆盖

### Who&When

| 真值类型 | 有标签记录 | 覆盖率 | 状态分布 |
|---|---:|---:|---|
| responsibility_agents | 184/184 | 100.00% | `{"direct": 184}` |
| responsibility_steps | 184/184 | 100.00% | `{"direct": 184}` |
| root_cause_nodes | 184/184 | 100.00% | `{"derived": 184}` |
| propagation_edges | 0/184 | 0.00% | `{"abstain": 184}` |
| causal_paths | 0/184 | 0.00% | `{"abstain": 184}` |
### TRAIL

| 真值类型 | 有标签记录 | 覆盖率 | 状态分布 |
|---|---:|---:|---|
| responsibility_agents | 0/148 | 0.00% | `{"abstain": 148}` |
| responsibility_steps | 144/148 | 97.30% | `{"abstain": 4, "partial": 144}` |
| root_cause_nodes | 0/148 | 0.00% | `{"abstain": 148}` |
| propagation_edges | 0/148 | 0.00% | `{"abstain": 148}` |
| causal_paths | 0/148 | 0.00% | `{"abstain": 148}` |
### AgentTrace

| 真值类型 | 有标签记录 | 覆盖率 | 状态分布 |
|---|---:|---:|---|
| responsibility_agents | 550/550 | 100.00% | `{"derived": 550}` |
| responsibility_steps | 550/550 | 100.00% | `{"derived": 550}` |
| root_cause_nodes | 550/550 | 100.00% | `{"direct": 550}` |
| propagation_edges | 550/550 | 100.00% | `{"derived": 549, "partial": 1}` |
| causal_paths | 550/550 | 100.00% | `{"direct": 550}` |

## 解释边界

- Who&When 的相邻 history 只形成时间顺序边，不声称错误传播边。
- TRAIL 的错误 span 标为 `partial` responsibility step，不提升为决定性根因。
- AgentTrace 的传播边只有在 causal path 的相邻节点能匹配原始图边时才记为 `derived`。
- 本报告评价数据兼容性，不评价任何归因算法的准确率。
