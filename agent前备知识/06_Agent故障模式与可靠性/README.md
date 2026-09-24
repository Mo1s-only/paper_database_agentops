# 第 6 章：Agent 故障模式与可靠性

本章正文：[详细教程](详细教程.md)；学习后完成：[练习与验收](练习与验收.md)；最后对照：[练习与验收答案](练习与验收答案.md)。

## 本章定位

故障归因的前提是稳定地定义失败。最终答案错误只是结果层现象；同一结果可能来自模型、工具、通信、编排、环境或评价器。

## 学习目标

- 区分 error、fault、failure、incident 和 risk。
- 建立结果层、步骤层、Agent 层、交互层、系统层的失败分类。
- 理解静默错误、部分失败、级联失败、错误放大、循环与掉队。
- 理解检测、归因、诊断、恢复和预防的区别。
- 理解超时、重试、降级、回滚、熔断和人工介入。

## 建议的分层分类

| 层 | 典型失败 | 可观察证据 |
|---|---|---|
| 任务结果 | 答案错误、约束未满足 | outcome、可执行判据 |
| 模型/推理 | 幻觉、错误计划、遗漏 | prompt/response、状态变化 |
| 工具 | 显式错误、静默错误、重复副作用 | tool result、文件/DB/网络事实 |
| 通信/协作 | 丢失、误传、冲突、错误放大 | message、handoff、依赖边 |
| 控制流 | 循环、提前停止、错误重试 | operation tree、step 序列 |
| 系统 | 资源耗尽、进程异常、网络故障 | CPU/RSS、exit、timeout、endpoint |
| 评价 | judge 偏差、错误真值 | evaluator log、人类/规则对照 |

## 责任与根因

最早发生的异常、最后输出错误的 Agent、影响最大的步骤和可修复的根因可能不是同一个对象。不要在分类阶段提前假定责任。

## 项目内材料

- `Reference paper/02_failure_attribution/MAST_Why_Do_Multi_Agent_LLM_Systems_Fail_text.txt`
- [Which Agent 精读笔记](../../Reference paper/02_failure_attribution/WhichAgentCausesTaskFailures_论文精读笔记.md)
- `Reference paper/03_diagnosis_localization/Tools_Fail_Detecting_Silent_Errors_in_Faulty_Tools_EMNLP2024.pdf`
- [推理循环案例](../../lab/agentsight/docs/experiment/case-study/reasoning-loop-detection/README.md)
- [指标体系总览](../../my_paper/metric/指标体系总览.md)

## 本章完成标准

对一条失败轨迹，能分别标注“表面失败、候选故障、传播路径、责任对象、候选根因、可验证修复”，并允许多因果和不确定标签。
