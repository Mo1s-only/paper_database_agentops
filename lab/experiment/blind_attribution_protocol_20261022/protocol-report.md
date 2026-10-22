# 标签盲预测协议零 API 检查

日期：2026-10-22  
状态：**VERIFIED（仅限本组合成协议检查）**；不是论文主实验结果。

## 目的

检查预测端是否能仅用规范化 trace 生成责任动作/Agent/Step/Edge 候选，之后由独立进程读取 ground truth 评分；并检查歧义及关键证据缺失时能否 abstain。未调用模型或 API。

## 运行隔离

- 夹具来自已有 `run_fault_matrix.py` 的三类确定性合成场景，每类 3 次，共 9 条。fixture 文件将 `run_id` 改为不透明编号 `blind-0001`…`blind-0009`，移除生成器 attributes；truth 单独保存在 `ground_truth.json`。
- 预测器入口为 `predict(trace)`，无任务名、故障类别或 truth 参数。`predict` 命令只读取 `trace.jsonl`，独占创建 `prediction.json`。
- 评分命令在预测冻结后以新 Python 进程单独运行，读取 `prediction.json` 与 `ground_truth.json`，独占创建 `score.json`。
- 自动化检查：trace 内没有 `silent_tool_error`、`error_propagation`、`routing_role_error` 或 `task_family`；prediction 内没有故障/任务/truth 标签字段。

## 结果

| 合成场景（仅评分分组） | N | Agent exact | Step exact | Action exact | Edge exact | Abstain |
|---|---:|---:|---:|---:|---:|---:|
| 静默工具错误 | 3 | 3/3 | 3/3 | 3/3 | 3/3 | 0/3 |
| 工具错误传播 | 3 | 3/3 | 3/3 | 3/3 | 3/3 | 0/3 |
| 路由/角色错误 | 3 | 3/3 | 3/3 | 3/3 | 3/3 | 0/3 |
| 合计 | 9 | 9/9 | 9/9 | 9/9 | 9/9 | 0/9 |

另有 6 项单测通过：trace-only 接口、三种 fixture 形状、双候选拒答、父事件缺失拒答、缺少契约时不误判、加入误导性故障字段不改变预测。

## 解释边界与问题

这是非常小的确定性、规则可见合成集，且三类候选结构在 schema 中很明显。结果只验证接口隔离和一组规则行为，不衡量自然轨迹准确率、不证明 eBPF 证据增益，也不证明故障类别未知条件下的泛化。固定规则本身仍带有对当前 schema 的归纳偏置。

本次发现旧 ground truth 对路由任务没有显式 `responsible_action_event_id`，只存责任边；新夹具补充了 action event id。旧格式评分器不会从边端点猜动作，缺少该标签时 action 项返回不可评分。

旧 `evaluation_gate/cross_task_counterfactual.py` 的预测、任务判据与干预仍读取 `task_name/spec`；其反事实结果尚未通过盲测隔离。本轮没有验证 repair/control 的独立因果判据，不能报告新的反事实成功率。

## 再现

从仓库根目录：

```powershell
python -m unittest -v my_paper_coding/failure_pilot/test_blind_attribution_eval.py
python my_paper_coding/failure_pilot/prepare_blind_fixtures.py --out-dir lab/experiment/blind_attribution_protocol_20261022-repro --repetitions 3
```

之后对每个 run 先单独调用 `blind_attribution_eval.py predict`，全部 prediction 冻结后再调用 `blind_attribution_eval.py score`。输出使用独占创建；若目标存在，另选新目录，勿覆盖本次冻结记录。

原始逐例输入、真值、预测和评分均留在本目录各 `blind-####/` 子目录中。

## 下一闸门

先修订跨任务反事实协议，让干预选择只由冻结 prediction 的候选输出决定；干预可执行判据应由独立任务 oracle 检验，不能让 scorer 的故障类别分支替预测器作答。然后盘点真实 run 的语义-only 与跨层证据视图是否能从原始工件重建，再设计同运行成对消融。付费 API 运行不属于本次检查，也没有执行。
