# experiment_20261013_13：原生 PID namespace 身份与时钟下界实测

本实验继续收紧归因前观测链，目标是把应用看到的 PID 与 AgentSight/eBPF 看到的 PID 从间接推断提升为内核直接证据，并确认时钟不确定度不会被记录为不真实的 0 ns。实验不生成根因、责任标签或因果路径。

## 执行结果

- 本地原生采集：`PASS`，网络调用 0 次。
- 真实多 Agent API 阶段：`BLOCKED`。成本台账已累计 2.183708 USD；两次计划会话的最坏预算为 0.10 USD，预计累计 2.283708 USD，超过 2.00 USD 硬停止线。
- 回归检查：Trace Adapter 101/101；BPF runtime 7/7；AgentSight capture core 44 通过、1 ignored，public API 1/1；BPF 单元组 3/3、63/63、48/48、49/49、17/17。

## 关键证据

同一个标记进程在 initial PID namespace 中的 TGID 为 `1791`，在采集器指定 PID namespace 中为 `34`，而用户态实际 PID 也是 `34`。该映射来自 `bpf_get_ns_current_pid_tgid`，因此记录为：

```text
bpf.pidns.tgid=1791,34
mapping_status=accepted
```

同一事件的原始 boot-relative 时间为 `623900254940 ns`，boot epoch 锚点为 `1791870003149853200 ns`，锚点不确定度下界为 `1 ns`。转换方法明确为 `boot_epoch_ns_plus_bpf_ktime_ns`。

机器可读结论见 [native-identity-verification.json](native-identity-verification.json)，构建与测试汇总见 [implementation-verification.json](implementation-verification.json)，模型调用采集准备度见 [model-context-readiness.json](model-context-readiness.json)，执行计划与成本门分别见 [plan.json](plan.json) 和 [budget-preflight.json](budget-preflight.json)。

## 可复现方式

本地采集入口为 [run-local-native-identity.sh](run-local-native-identity.sh)。它启动 release 版 AgentSight process debugger，再启动带唯一 marker 的进程。校验器按 marker 唯一定位 EXEC 事件，并同时检查双 PID、用户态 PID、非零时钟下界和转换声明。

## 证据边界

### VERIFIED

- 单进程、单会话下，eBPF 可在同一事件中给出 initial namespace TGID 与指定 namespace TGID。
- 本次 `1791 → 34` 映射唯一，且 `34` 与用户态 PID 一致。
- 时钟锚点不确定度为正值，原生时钟转换公式已记录。
- 统一事件协议允许该直接映射标为 `accepted`，并拒绝缺项或歧义映射。
- 控制式模型调用采集器已能在请求前冻结模型版本、采样参数、system prompt 哈希、tool schema 哈希和单调时钟，并在响应后绑定 provider response ID。

### INFERRED

- 该机制预计可直接替换历史真实会话中的 session/comm/launch interval 间接 PID 对齐；由于本次没有发起新的付费会话，此结论尚未由真实多 Agent API 运行确认。

### UNVERIFIED

- 两个并发真实 Agent 会话中，直接 PID 映射是否都能唯一闭合。
- 真实 provider 响应中模型版本与 response ID 是否能按控制式调用上下文协议完整保存。
- 长会话、进程重启和 PID 重用条件下的映射稳定性。

### AUTHOR_INPUT_NEEDED

- 如需立刻执行计划中的两次真实 API 会话，需要明确提高累计成本硬上限；最低应高于预计的 2.283708 USD。

## 下一研究闸门

在新的预算上限下运行两次受控真实会话。两次都必须同时满足：直接 PID namespace 证据、非零时钟不确定度、完整模型调用上下文和可重放查询收据；任一项缺失都不能进入归因阶段。
