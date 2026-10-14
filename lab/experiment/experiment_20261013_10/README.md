# experiment_20261013_10｜归因前可查询证据包

## 目标

将 RCACopilot 的可组合证据采集、OpenRCA 的程序化查询、Watson 的镜像条件约束和 OpenRCA 2.0 的逐项证据收据，落到当前归因前观测链。输出只描述观测到的身份、生命周期和工具结构，不生成根因、责任或因果路径。

## 输入

- `VERIFIED`：`experiment_20261012_14` 的一次真实 Claude Code API 会话，共 6 条协议 v0.2 事件、1 个闭合 session、1 个闭合 step 和 1 个闭合 tool call。
- `VERIFIED`：输入事件 SHA256 为 `f9fb7a628866c127f27749d95b582e4697cd3ce133f7eade7a16aa572a5c47b0`。
- `VERIFIED`：复用 `experiment_20261012_16` 的归因前统一门；身份/工具图可用，严格有界跨层时间排序不可用。
- 本实验没有重新调用 API；`network_calls=0`。输入不是合成数据，而是已有真实 API 会话的确定性回放。

## 结果

- `VERIFIED`：生成 4 个证据通道、5 个可执行精确查询和 3 条观察关系。
- `VERIFIED`：5/5 查询在原始事件流上重放成功，事件 ID 与结果 SHA256 均一致。
- `VERIFIED`：3/3 观察关系都有事件收据与查询收据；两条为直接结构证据，一条进程关系保持 `inferred`。
- `VERIFIED`：工具生命周期由事件 `4021bac3-5995-4e9b-865f-3773cfaa16f0` 与 `d752b8dd-b67b-4a52-a3cb-b9a5dc98d00e` 直接闭合。
- `VERIFIED`：根因、责任、因果路径三个输出标志均为 `false`；回放验证器会拒绝被篡改的查询哈希或越界结论。
- `VERIFIED`：Python 完整测试集 89 项通过，其中包含两个 session 交错且复用局部 step/tool ID 的隔离测试。

## 证据状态与边界

- `INFERRED`：session 与 observer process 的关系仍依赖 session、进程名、启动区间和共享 tool ID，没有直接 `NSpid` 真值。
- `UNVERIFIED`：历史工具事件中的 observer uncertainty 为 0 ns，缺少系统分辨率下界；因此只记录 `sequence_only`，不声称严格跨层先后。
- `AUTHOR_INPUT_NEEDED`：若后续要启用 Watson 式事后推理重建，新的真实会话必须采集模型标识与版本、temperature、top_p、系统提示词哈希、工具 schema 哈希以及可核验的请求—响应配对。本实验不会用默认值补造这些字段。

机器可读证据见 [pre-attribution-evidence-package.json](pre-attribution-evidence-package.json)，独立回放结果见 [query-replay-verification.json](query-replay-verification.json)。
