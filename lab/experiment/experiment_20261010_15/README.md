# experiment_20261010_15｜高精度时钟与应用事件协议 v0.2

## 目标

使用本地源码构建的 AgentSight 完成一次低成本真实 API 会话，验证：

- `bpf_ktime_get_ns()` 通过纳秒级 boot epoch 锚点换算后，进程启动时间无需整秒小数补偿即可落入应用启动边界；
- AgentSight `tool_calls` 同时保存原始 boot-relative 纳秒时间、boot epoch 锚点及锚点不确定度；
- 应用事件协议 v0.2 同时保存本地 PID、观测器 PID、两个 PID 域、映射依据、应用三时钟锚点和观测器原始时钟。

## 预算

只运行 1 个真实 Claude Code CLI 会话，单会话预算上限 0.10 USD，不自动重试。实验前累计 CLI 报告费用为 1.601149 USD，计划最坏累计值为 1.701149 USD，低于 2.00 USD 硬停止线。

## API 调用前证据状态

- `VERIFIED`：实验目录、计划、协议代码和 AgentSight 修改均在 API 调用前建立。
- `UNVERIFIED`：源码是否能成功构建；原始 boot 时间是否会进入 SQLite；修复后二进制的实测启动时间是否落入 Popen 边界。

## 结果：部分成功

- `VERIFIED`：真实 API 会话一次成功，费用 0.024867 USD；原生工具生命周期闭合，AgentSight 同一 tool_call ID 唯一命中。
- `VERIFIED`：纳秒级 boot epoch 换算生效，进程启动时间 1791620128737 ms 落在 Popen 区间 1791620128735.0967–1791620128737.6318 ms 内，追加校正为 0。
- `FAILED_GATE`：工具行的 `observer_raw_boot_ns`、`observer_boot_epoch_ns` 和 `observer_clock_uncertainty_ns` 均为空，epoch 公式无法复算，协议 v0.2 没有在本次运行闭环。
- `INFERRED`：后续源码检查将缺失定位到 SSE 聚合事件没有透传 `_agentsight_clock`；这一解释在 `experiment_20261012_14` 的修复后实测中得到支持。

因此本实验只证明“进程时钟修复成功”，没有证明“SSE 工具时钟持久化成功”，状态保持为部分成功。原始结果位于受 `.gitignore` 保护的 `results/`，可提交证据见 `analysis.json` 与 `实验报告.md`。
