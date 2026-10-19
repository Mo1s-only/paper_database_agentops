# R03 — AgentTrace: Causal Graph Tracing：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文、官方标签和本地文件）。`

本地论文：[01_agent_observation/AgentTrace_Causal_Graph_Tracing.pdf](<../../01_agent_observation/AgentTrace_Causal_Graph_Tracing.pdf>)

## 分类

合成多智能体轨迹；因果图与根因节点标注

## 论文实验使用的数据

论文构造 10 个领域、550 个场景的合成基准。官方 ICLR 2026 workshop artifact 的 data 目录还包含场景、真值和部分结果文件，因此本地文件数会多于 550。

## 获取与本地状态

官方仓库标签 iclr2026-aiwild-camera-ready，固定提交 323fc63。已下载该标签的 data 目录。

## 本地数据

- [`shared_data/AgentTrace_ICLR2026_data`](../shared_data/AgentTrace_ICLR2026_data)

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [官方仓库](https://github.com/GeoffreyWang1117/AgentTrace)

## 对当前论文的用途

可用于验证事件到因果图的结构转换、根因节点排序和场景级可重放；不能把仓库中的模型输出当作独立人工真值。
