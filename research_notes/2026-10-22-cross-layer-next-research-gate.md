# 研究决策记录：跨层数据链之后的下一步

日期：2026-10-22  
主题：从跨层采集/关联验证推进到 AgentOps 故障归因有效性验证

## 当前证据

### VERIFIED

- 本轮对 AgentTrace、Who&When、TRAIL GAIA 各取 1 个数据集派生样本，完成了真实 Claude API 回放采集。
- 三次样本均捕获到 Claude 原生工具调用、AgentSight 的 LLM/tool/token 记录及 eBPF 进程事件；adapter 的 session+tool 关联均接受 1/1。
- 带 hook 的受控桥接把 Claude tool-call ID 写入带标签的 Bash 命令，再由 eBPF 观察进程命令与父子进程关系；该受控进程链 3/3 成功。
- 三次 CLI 报告费用合计 $0.0638544，按实验规划汇率 10 CNY/USD 约 ¥0.638544；这是 CLI 报告值，尚非供应商账单核验值。
- adapter 测试 137/137 通过。
- 结果已记入 `lab/experiment/public_dataset_cross_layer_20261022/跨层数据链真实API验证报告.md`。

### INFERRED

- 当前证据支持“在这些受控回放样本与采集配置下，数据链能够跨三个数据集来源运行”，但样本量每家族仅 1，不能据此声称泛化已充分验证。
- hook 传递的工具 ID 是实验辅助的显式身份桥。它证明受控场景下可建立进程级链路，不等于 AgentSight 被动观测天然包含 Claude tool-call ID，也不能把它作为纯被动关联能力的证据。
- 这些实验验证的是采集和关联，不是故障归因准确率、因果效应或相较基线的提升。

### UNVERIFIED / 尚缺证据

- 多样本、多次运行下各层事件捕获和关联的稳定性，以及精确率、召回率和 abstention 行为。
- 跨层证据是否能提高故障责任步骤/agent 的归因准确率，及其相对语义层单独、AgentSight 单独等基线的增益。
- 对自然任务与受控注入故障的适用边界、运行开销以及外部账单费用。

## 用户确认的主评价目标

2026-10-22 用户确认：下一阶段以“跨层证据能否提升故障归因准确率”为主评价目标，采集/关联可靠性作为前置指标。

## 代码审计发现：旧 9/9 不是盲测准确率

### VERIFIED

- `my_paper_coding/failure_pilot/run_fault_matrix.py` 的 `infer(trace, fault)` 接收了真值中的 `fault_type`，再按 `silent_tool_error`、`error_propagation`、`routing_role_error` 选择不同规则。对应 `my_paper_coding/failure_pilot/fault-matrix-report.md` 的 9/9 结果因此不能解释为一个未知故障类别下的通用盲测归因准确率。
- `my_paper_coding/evaluation_gate/cross_task_counterfactual.py` 的 `infer`、`evaluate` 和 `counterfactual` 也读取 `task_name/spec`；原 9/9 归因及反事实翻转不属于标签盲测或独立验证。
- `my_paper_coding/failure_pilot/analyze_failure_pilot.py` 也有适用范围限制：其规则针对静默库存错误字段，不是通用多故障归因器。
- `my_paper_coding/evaluation_gate/gate-report.md` 已注明旧结果来自确定性本地 harness，且不等于真实 AgentSight 轨迹上的因果效应。
- `my_paper_coding/public_dataset_adapters/ground_truth_protocol.md` 对标签边界作了保守约束：Who&When 有直接责任 Agent/Step 标签；TRAIL 的 error span 只能作为 partial；AgentTrace 有 root-cause/path 标注。但这些历史数据没有本项目新回放时的 PID/tool-call ID，不能直接充作新运行的跨层真值。

## 推荐研究问题与实验闸门

- **RQ**：在有独立责任真值的可复现多 Agent 故障中，加入 AgentSight/eBPF 系统证据及可审计跨层关系，是否相较于语义日志单独可提高责任 Agent/步骤识别，并降低歧义/错误归因？
- **Object**：多 Agent 工作流中的三类责任位置——静默工具错误、错误传播、路由/角色错误；分别区分“故障产生位置”“错误传播位置”和“最终失败表现”。
- **Intervention**：同一运行的轨迹做输入消融：B0 仅最终结果；B1 语义日志/原生工具事件；B2 AgentSight/eBPF 系统观测；B3 语义+系统证据经 adapter 关联；B4 hook 显式携带 tool ID 的受控上界（单列，不能作为被动能力）。所有方法看不到 fault_type 和 ground-truth 文件。
- **Measurement**：前置门统计原生工具捕获率、AgentSight ID 精确匹配率、跨层关系 precision/recall 与 abstention；主指标为责任 Agent/Step top-1 exact match、错误归因率、可判定覆盖率；辅以边/传播定位、证据可复核率、运行开销与费用。拒答应作为覆盖率单列，不能简单算正确。
- **Baseline**：B1 semantic-only 是主要对照；B0 final-output-only 与 B2 system-only 用于定位各层能力；B3 为待验证的组合方法；B4 是显式插桩上界。所有组在同一 trace、同一 frozen truth 上评估，禁止将故障类型作为算法输入。
- **Boundary**：这是受控故障注入验证，不自动代表开放世界基准或自然生产故障；三个公开数据集当前用于标签兼容/补充离线分析，不把重新执行的 probe 说成原 benchmark 的真实运行轨迹。

### 建议执行顺序

1. 先改/补一套不读 fault_type 的统一评测入口；把真值文件独立保留，只由评分器在预测完成后加载。对故障位置标签采用双层定义：`fault_origin` 与 `responsibility_action`，避免把外部工具超时与 Agent 未恢复/错误传播混为一个“根因”。
2. 用现有 9 条本地矩阵数据做协议单元测试和消融管线试跑，但重新标记为“协议/实现验证”，不沿用 9/9 作为论文结果。
3. 用既有真实 AgentSight 两 Agent error-propagation 运行验证归一化和 B0–B4 的输入隔离；若现存 artifact 不含某个 ablation 所需信号，则明确记录缺项，不补造。
4. 再做 3 类故障 × 至少 3 次独立运行的受控 AgentSight 采集；每次预注册/冻结场景与真值、保存未加工日志和输入哈希。只有采集门通过的 run 才进入归因评分；hook 组独立标识。
5. 检查同一场景内 B1 对 B3 的配对差异，并报告逐类结果、置信区间/小样本限制与失败案例。若 B3 未优于 B1，不强行宣称准确率提升，转而报告适用故障类别和证据链贡献。

## 实验假设

**H1（待验证）**：在故障产生与失败表现跨 agent/进程边界，且语义日志不足以区分候选步骤的场景中，B3 相较 B1 提高责任 Agent/Step 的 top-1 准确率或降低错误归因率；在纯路由错误等系统层未提供判别信息的类别中，组合方法可能无增益。此差异性也是结果，应按故障类别报告。

**状态更新（2026-10-22）**：trace-only 预测、独立评分与盲化 repair/control 已实现；10 项单测通过，两组 9 条脱标签合成夹具通过，详见 `lab/experiment/blind_attribution_protocol_20261022/protocol-report.md` 与 `lab/experiment/blind_counterfactual_protocol_20261022/protocol-report.md`。这只关闭最小接口/隔离闸门；真实证据消融尚未启动。

**下一研究闸门**：盘点历史真实 run 能否重建 B1/B3 成对输入及来源状态；之后才决定真实重放规模与 API 预算。

## 决策记录

- 主评价目标确认：验证跨层证据是否提升故障归因准确率。
- 对应前置门：采集/关联可靠性。
- 是否立即进行下一批真实 API 运行：未授权/未决定；当前建议先修正盲测评测协议并做离线验证。
