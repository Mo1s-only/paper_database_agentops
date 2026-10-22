# 标签盲归因与修复/无关控制协议检查

日期：2026-10-22  
状态：**VERIFIED（仅限本组合成协议检查）**；不是论文主实验结果，不是真实 AgentSight 实验。

## 目的与隔离

对库存工具错误、服务工具超时、错误路由三类确定性任务各生成 3 条合成轨迹。预测器只接收 trace；真值与 repair plan 单独保存。预测文件冻结后，再以独立进程运行反事实验证和独立评分。

- trace 中使用 `cf-blind-####` 不透明运行 ID，移除注入器 attributes 和故障/任务类别。
- `blind_attribution_eval.py predict` 不读取 truth 或 repair plan。
- `blind_counterfactual.py` 不读取 task/fault name；只有预测候选与预登记 repair plan 的目标事件一致时，才执行修复/控制重放。成功判据从 trace 的 task-start contract 泛化计算。
- `blind_attribution_eval.py score` 在预测和反事实输出冻结后独立读取 truth。
- 自动扫描：trace 不含故障名/task-family；prediction 不含故障名、任务名或 ground-truth 字段。
- 全程零 API、零网络调用。

## 结果

| 合成故障组（评分后分组） | N | Agent | Step | Action | Edge | repair 成功 | 无关控制仍失败 | CF flip | abstain |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 静默工具错误 | 3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 0/3 |
| 工具错误传播/超时 | 3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 0/3 |
| 路由/角色错误 | 3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 0/3 |
| 合计 | 9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 0/9 |

9 个 unittest 测试方法通过，覆盖 11 个子场景：6 个 trace-only 测试、3 类跨任务 contract repair/control 测试、候选目标不一致保护，以及跨 run 计划拒绝。

## 解释边界

本检查验证预测、干预计划、任务 oracle 和 scorer 在代码接口上可以分离，并检查预登记的合成修复能使 contract oracle 通过、无关控制不能通过。场景由同一测试作者构造、契约和规则显式可见，故 9/9 不是盲测方法准确率、统计泛化或真实因果效应；真实任务上还需要独立注入清单、任务 oracle、运行时轨迹、盲化标签和可执行修复操作。

旧 `evaluation_gate/cross_task_counterfactual.py` 未被覆盖，其 9/9 继续作为历史标签条件 harness 记录，不可引用为新的 CF 效果。新协议的逐例 trace、truth、repair plan、prediction、counterfactual 和 score 均冻结在各子目录。

## 再现

```powershell
python -m unittest -v my_paper_coding/failure_pilot/test_blind_attribution_eval.py
python -m unittest discover -s my_paper_coding/evaluation_gate -p test_blind_counterfactual.py -v
python my_paper_coding/evaluation_gate/prepare_blind_counterfactual_fixtures.py --out-dir lab/experiment/blind_counterfactual_protocol_20261022-repro --repetitions 3
```

每个 run 依次独立调用 `blind_attribution_eval.py predict`、`blind_counterfactual.py`、`blind_attribution_eval.py score`。所有输出独占创建；已有目录不可覆盖。

## 下一闸门

协议层面已经可以区分预测、预登记干预和评分。下一步不是扩大合成数量，而是审计历史真实运行工件能否在不补造数据的前提下重建成对语义-only 与语义+系统输入；量化 direct / inferred / missing / conflict 关系。只有找到配对、来源可追溯的真实 run，才能设计真实 AgentSight/eBPF 证据效用实验。
