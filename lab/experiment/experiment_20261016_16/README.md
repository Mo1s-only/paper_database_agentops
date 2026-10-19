# experiment_20261016_16：公开归因数据统一协议兼容性实验

本实验执行归因前计划的前三步：为 Who&When、TRAIL、AgentTrace 编写适配器，建立五类归因真值协议，并在全部本地公开数据上测量字段覆盖、关系重建、证据完整与拒绝情况。网络/API 调用为 0。

## 最终结果

- 输入：Who&When 184 条、TRAIL 148 条、AgentTrace 550 条，共 882 条记录。
- 882/882 记录通过 `attribution-benchmark-record-v0.1` 内置严格校验。
- 14,697/14,697 个源结构关系机会被重建。
- 31,132/31,132 个 Step、Relation 和非拒绝真值对象具有源路径、JSON Pointer 和源记录 SHA-256。
- 五类真值槽位的总体 `abstain` 率为 21.86%。这是源数据未提供相应粒度标签的边界，不是适配失败率。
- 旧 Trace Adapter 101/101 测试通过；新增适配器 4/4 测试通过。

详细结果见 [`results_r3/compatibility-report.md`](results_r3/compatibility-report.md)，机器可读结果见 [`results_r3/compatibility-report.json`](results_r3/compatibility-report.json)，运行与文件哈希见 [`run-manifest.json`](run-manifest.json)。

## 三次运行

1. `results/`：失败。TRAIL 的 `a96c...json` 含尾随逗号，不是严格 JSON。
2. `results_r2/`：失败。TRAIL 的 `7282...json` 重复使用同一 `span_id`，初版统一 ID 校验拒绝覆盖。
3. `results_r3/`：通过。只对尾随逗号实施窄范围修复并保留原始 SHA-256；重复 span 使用稳定序号 ID，能够由嵌套源路径消歧的父子关系继续重建，歧义标签保留为 `partial`。

前两次目录是中止时留下的部分输出，不能作为正式实验结果；正式结论只来自 `results_r3/`。

## 证据边界

### VERIFIED

- Who&When 可完整提供责任 Agent 和决定性 Step，但没有传播边或完整路径标签。
- TRAIL 可提供错误 span；144/148 条记录至少有一个可匹配错误位置，但这些位置不能自动提升为决定性根因。
- AgentTrace 的 550 条合成轨迹都具有根因节点和因果路径；其中 549 条路径的相邻节点全部匹配显式图边，1 条仅部分匹配。
- 公开数据之间的互补性可以由统一协议表示，缺失标签可以显式 `abstain`。

### INFERRED

- 当前 schema 足以承载 Agent/Step/Node/Edge/Path 五种评价粒度，可作为后续归因方法比较的公共输入层。
- 组合 Who&When 的决定性责任标签、TRAIL 的多错误 span 和 AgentTrace 的路径标签，比依赖单一数据集更适合检验归因层次。

### UNVERIFIED

- 统一结构是否会提高任何归因算法的准确率。
- 公开数据作者标签本身的正确性与跨数据集可比性。
- 合成 AgentTrace 路径上的结果能否迁移到真实多 Agent API 会话。
- 新真实会话中的直接 PID、时钟界、模型上下文和查询收据是否能同时闭合。

## 下一研究闸门

在进入归因方法比较前，先完成两次真实多 Agent 会话，要求每次都同时具有直接 PID namespace 映射、非零时钟不确定度、完整模型调用上下文和可重放查询收据。当前累计成本 2.183708 USD 已超过 2.00 USD 硬停止线，执行两次会话需把硬上限提高到至少 2.283708 USD。

