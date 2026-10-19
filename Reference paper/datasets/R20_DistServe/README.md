# R20 — DistServe：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文实验设置与官方仓库）。`

本地论文：[05_reliability_evaluation/DistServe.pdf](<../../05_reliability_evaluation/DistServe.pdf>)

## 分类

LLM 服务负载；SLO 与 goodput

## 论文实验使用的数据

使用 ShareGPT 聊天负载、HumanEval 代码补全、LongBench 摘要任务；由于原数据没有请求时间戳，论文用 Poisson 到达过程合成请求到达。

## 获取与本地状态

原始语料和系统复现实验依赖较多，未本地镜像。官方代码提供负载生成和服务实现入口。

## 本地数据

- 无。本次未下载的原因见“获取与本地状态”。

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [官方仓库](https://github.com/LLMServe/DistServe)

## 对当前论文的用途

用于设计 TTFT、TPOT、goodput 和并发负载维度；合成到达参数必须与数据内容分开记录。
