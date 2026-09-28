# P0 请求—响应配对 Pilot 汇总

> 本报告只统计带唯一 marker 的受控调用；不能替代并发、多请求和未标记调用的通用配对评测。

| 项目 | 结果 |
|---|---:|
| Pilot 运行数 | 5 |
| Agent 成功数 | 5 |
| `gate_pass` 数 | 5 |
| marker 配对候选数 | 5 |
| marker 配对成功数 | 5 |
| marker 配对 Precision | 1.000 |
| marker 配对 Recall | 1.000 |
| 响应延迟均值（ms） | 1892 |
| 响应延迟范围（ms） | 1262–2457 |

## 证据边界

- `VERIFIED`：本批次每条 marker 请求均找到包含同一 marker 的响应，且请求与响应共享观测 `pid/tid`。
- `UNVERIFIED`：并发请求、未标记请求、请求重试和多轮工具调用的通用配对性能。
- 下一闸门：将配对分析接入一个可重复的失败任务，并保留独立的责任 Agent/Step/Edge 真值。
