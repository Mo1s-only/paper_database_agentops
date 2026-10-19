# R01 — AgentMonitor：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文实验设置与官方仓库）；论文所用精确抽样 ID 未公开。`

本地论文：[01_agent_observation/AgentMonitor.pdf](<../../01_agent_observation/AgentMonitor.pdf>)

## 分类

通用推理/代码/安全；多智能体性能预测

## 论文实验使用的数据

HumanEval、MMLU、GSM8K，以及从 MINT 采样的代码/推理/数学任务；安全实验使用 BeaverTails、MaliciousInstruct、AdvBench，各采样 100 条。

## 获取与本地状态

这些是多个上游公开基准的组合。论文仓库公开，但未发现与论文抽样完全一致、带固定样本 ID 的统一数据包，因此没有重复下载全部通用基准。

## 本地数据

- 无。本次未下载的原因见“获取与本地状态”。

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [论文代码](https://github.com/chanchimin/AgentMonitor)
- [HumanEval](https://github.com/openai/human-eval)
- [GSM8K](https://github.com/openai/grade-school-math)
- [BeaverTails](https://huggingface.co/datasets/PKU-Alignment/BeaverTails)

## 对当前论文的用途

适合作为语义任务成功率与安全违规率基准；若复现，必须固定抽样 ID、随机种子和版本。
