# 文献索引与证据状态

状态说明：`core` = 当前方向核心；`supporting` = 支撑背景或方法；`candidate` = 已下载但需要精读；`contrast` = 可用于比较边界。分类是工作索引，不替代论文精读。

| ID | 文件/主题 | 主链路 | 年份/来源 | 状态 | 可用于 |
|---|---|---|---:|---|---|
| R01 | AgentOps | 观测 | 本地材料 | core | Agent 运行观测与运维链路 |
| R02 | AgentSight | 观测 | 本地材料 | core | 系统级捕获、过程和网络观测 |
| R03 | AgentMonitor | 观测 | 本地材料 | core | Agent 监测与运行时信号 |
| R04 | AgentTrace | 观测 | 本地材料 | supporting | trace 与因果链路 |
| R05 | TraceElephant | 故障归因 | ACL 2026 | core | 全执行轨迹归因基准 |
| R06 | Which Agent Causes Task Failures and When? | 故障归因 | OpenReview/本地材料 | core | Agent/时刻责任归因 |
| R07 | CDC-MAS | 故障归因 | 本地材料 | core | 多 Agent 故障归因 |
| R08 | EDGE | 故障归因 | 本地材料 | supporting | 错误依赖图与传播 |
| R09 | MAST | 故障归因 | 本地材料 | supporting | 多 Agent 失败分类 |
| R10 | Watson | 诊断定位 | 本地材料 | core | 旁路重建和认知诊断 |
| R11 | eInfer | 诊断定位 | 本地材料 | supporting | 推断/诊断线索 |
| R12 | Beyond Natural Language | 诊断定位 | 本地材料 | supporting | 非自然语言证据与诊断 |
| R13 | Tools Fail | 诊断定位 | EMNLP 2024 | candidate | 静默工具错误检测与恢复 |
| R14 | AgentDropout | 预测/早期预警 | 本地材料 | candidate | Agent 掉队/退出风险 |
| R15 | Breaking Agents | 预测/早期预警 | EMNLP 2025 | candidate | 故障诱导、风险暴露与防御 |
| R16 | DistServe | 可靠性与评测 | 本地材料 | contrast | 服务系统性能/稳定性对照 |
| R17 | AgentEval | 可靠性与评测 | EMNLP 2024 | candidate | Agent 应用任务效用验证 |

## 新增论文官方来源

- Tools Fail: <https://aclanthology.org/2024.emnlp-main.790/>；PDF：<https://aclanthology.org/2024.emnlp-main.790.pdf>
- AgentEval: <https://aclanthology.org/2024.emnlp-main.1219/>；PDF：<https://aclanthology.org/2024.emnlp-main.1219.pdf>
- Breaking Agents: <https://aclanthology.org/2025.emnlp-main.1771/>；PDF：<https://aclanthology.org/2025.emnlp-main.1771.pdf>
- TraceElephant: <https://aclanthology.org/2026.acl-long.912/>；本地已有文件，未重复下载。

下一道研究关口：先精读 R13、R15、R17，补齐“异常检测/风险预警—根因归因—任务效用评测”三者之间的指标映射，再决定论文实验是否需要新增预测模块。
