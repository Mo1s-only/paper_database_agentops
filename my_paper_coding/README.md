# AgentOps 论文实验代码

本目录保存论文原型、数据适配器、离线评测和可复现实验控制代码。研究主线是：在应用语义日志与系统级观测分源且可能不完整时，保留原始来源，并构造带证据引用、关系状态和缺失说明的跨层执行图。构图成功不等同于因果归因成立；只有独立真值、适当基线和反事实实验支持后，才能报告归因效果。

## 目录职责

| 目录 | 用途 | 当前证据边界 |
|---|---|---|
| `trace_adapter/` | Claude 原生事件与 AgentSight 事件的规范化、候选关联、provenance 和来源审计 | 已有真实运行输入及离线测试；直接关联、推断关联和 abstain 必须分开报告。不是已验证的通用归因器 |
| `failure_pilot/` | 确定性多 Agent 故障、独立责任真值和离线归因评分 | 可验证闭环与评测协议，不代表真实 Agent/API 的泛化效果 |
| `evaluation_gate/` | 跨任务的归因与反事实确定性 harness | 本地、零 API 的协议验证；不替代真实运行 |
| `p0_pairing/` | 唯一 marker 的请求—响应配对 pilot | 结果仅支持受控 marker 场景，不代表任意请求的通用配对率 |
| `public_dataset_adapters/` | 将公开轨迹映射到统一评测记录 | 只验证字段兼容性；数据集缺少的系统/eBPF 层不可由适配器补造 |
| `experiment_control/` | 预算预检、运行清单与成本审计工具 | 账本和 CLI 成本不能替代供应商最终账单；本目录不应保存明文密钥 |

原始实验输入和运行报告保存在 `lab/experiment/`，不应为了方便复制进代码目录。凭据只通过本机安全存储或受保护环境注入；不要把 API key、完整敏感 prompt/response 或含密钥日志提交到版本库。

## 当前研究状态

- **VERIFIED（限具体运行）**：run10 离线复核中，严格语义—运行时关联器将 4 个原生工具调用中的 2 个 Bash 调用建立为唯一的推断关系，2 个 Write 调用 abstain；这不是直接共享 ID 关联，也没有独立标注可计算 precision/recall。AgentSight LLM 响应体、`tool_calls` 或 `token_usage` 缺失仍须按来源缺口记录。
- **INFERRED**：进程血缘、受控时间窗、命令/目标路径等可形成有证据引用的跨层候选关系；若没有共享 ID 或足够唯一的受控锚点，不得标成直接 join。
- **UNVERIFIED**：provenance Adapter 是否能稳定优于并列查看或现有 PID/时间匹配、跨层证据是否提升责任边定位、方法是否可泛化。
- **当前闸门**：先用已有输入完成零 API 的分源规范化、关系审计和扰动测试；此闸门不要求先修复 AgentSight 的 HTTP 响应体解析，也不授权新增真实 API 调用。

## 离线验证

在仓库根目录运行 Trace Adapter 回归测试：

```powershell
python -m unittest discover -s my_paper_coding/trace_adapter -p 'test_*.py' -v
```

公开数据适配器与控制器测试可分别运行：

```powershell
python -m unittest my_paper_coding.public_dataset_adapters.test_adapters -v
python -m unittest discover -s my_paper_coding/experiment_control -p 'test_*.py' -v
```

对已有运行做候选对齐与 SQLite 来源审计时，必须使用新的、尚不存在的输出目录；脚本拒绝覆盖：

```powershell
$adapterRoot = 'my_paper_coding/trace_adapter'
$runDir = 'lab/experiment/experiment_20261021_24_agentsight_candidate_mock/real-canary-20261021-10/alignment-inputs'
$adapterOut = "$adapterRoot/alignment_runs/review-20261021-run10"
python "$adapterRoot/align_candidates.py" --manifest "$runDir/run.json" --evidence "$runDir/evidence-events.jsonl" --output $adapterOut
python "$adapterRoot/audit_alignment.py" --manifest "$runDir/run.json" --evidence "$runDir/evidence-events.jsonl" --output "$adapterOut/audit-report.json"
$strictOut = "$adapterOut/strict-link-report.json"
python "$adapterRoot/strict_semantic_runtime_linker.py" --run 'lab/experiment/experiment_20261021_24_agentsight_candidate_mock/real-canary-20261021-10' --output $strictOut
```

`accepted` 仅表示观测关联规则接受该候选，不表示已证明责任或因果；`uncertain`/`abstain` 是有效结果，不应为追求覆盖率而强行补边。审计中的合成扰动验证软件是否 fail-closed，不是新增真实样本或准确率证据。评测真值只在独立评分阶段读取，不能进入事件构造或候选生成。

## 实验记录要求

每项新增实验应记录目的、冻结输入及哈希、数据/任务与版本、采集源和转换步骤、运行命令、代码版本、输出路径、关系覆盖及缺失统计、预算与成本（若涉及 API）、当前结论和局限。结果须标注为 `VERIFIED`、`INFERRED`、`UNVERIFIED` 或 `AUTHOR_INPUT_NEEDED`，并明确单次 pilot 不支持的推广范围。

真实 API 只用于回答离线方法无法回答的问题；每次调用都必须经过单次预算预检和明确授权。Adapter 单元测试、关系拒绝/扰动测试和已有数据重放应优先保持零 API。
