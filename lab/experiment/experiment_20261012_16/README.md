# experiment_20261012_16｜归因前身份决策与观测完整性收口

## 目标

本实验不实现归因，也不发起 API 调用。它把归因之前的观测层补成可审计的输入门：

1. 明确定义 PID 映射 `accepted / inferred / abstain` 三态决策；
2. 只有 `/proc/*/status` 的 `NSpid` 直接证据才能产生 `accepted`；
3. 用两个并发 PID namespace 验证相同内层 PID 会产生歧义，缺少 namespace 时必须 abstain；
4. 为真实协议流报告身份字段、进程字段、应用时钟、工具观测时钟和生命周期完整率；
5. 在报告中固定输入和关键实现代码哈希。

## 边界

- `VERIFIED`：使用本地 namespace 夹具和已保存的真实六事件流，网络调用数固定为 0。
- `UNVERIFIED`：真实 Claude 会话没有历史 `NSpid`，其 PID 关系继续保持 inferred。
- 本实验只判断证据是否足以建立观测身份，不输出责任 Agent、责任步骤或根因。

## 一键验证

```powershell
python my_paper_coding/trace_adapter/pre_attribution_gate.py --quality-report lab/experiment/experiment_20261012_16/observation-quality-report-final.json --analysis lab/experiment/experiment_20261012_14/analysis.json --namespace-matrix lab/experiment/experiment_20261012_16/pid-namespace-matrix-final.json --output lab/experiment/experiment_20261012_16/results/pre-attribution-gate-rerun.json
```

最终结果以 `pid-namespace-matrix-final.json`、`observation-quality-report-final.json`、`pre-attribution-gate.json` 和 `verification.json` 为准。
