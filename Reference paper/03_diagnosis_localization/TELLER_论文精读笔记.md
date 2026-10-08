# TELLER 论文精读笔记

## 论文信息

- 标题：TELLER: Non-intrusive Cross-Layer Root-Cause Analysis for LLM Inference
- 作者：Ruilin Xu、Junyi Li、Pengfei Chen、Zongxuan Xie
- Venue/年份：ASE 2026 Research Papers
- 官方来源：[ASE 2026](https://conf.researchr.org/details/ase-2026/ase-2026-research-track/144/TELLER-Non-intrusive-Cross-Layer-Root-Cause-Analysis-for-LLM-Inference)
- 本地论文：`TELLER_Non_intrusive_Cross_Layer_RCA_LLM_Inference_ASE2026.pdf`
- 阅读目的：跨层 trace-log 对齐、调用链重建和 RCA 模态消融
- 状态：精读；发表状态 `VERIFIED`

## 1. One-sentence contribution

TELLER 在不修改模型二进制的条件下采集 NVTX/CUPTI trace 和服务日志，重建请求级调用链，并用结构保持的 Trace Pair Encoding 支持 LLM 推理服务的跨层根因分析。

## 2. Problem setting

目标是 LLM inference service 的请求级 RCA。一个请求可能跨越 Python/C++ 后端、CUDA API、GPU kernel 和多节点通信；trace 精确但低层且庞大，日志有语义但和具体 operator 脱节。

## 3. Method core

TELLER 先将 NVTX/CUPTI 事件组织成调用链，再以时间、父子关系、线程和通信关系把日志对齐到请求。随后构造 dependency-aware causal-context slice，并用 Trace Pair Encoding 压缩父节点、深度、持续时间等结构信息。数值候选定位与多模态模型共同输出异常步骤、可疑 operator 和解释。

## 4. Evidence

- 双节点、六张 A40 GPU，Qwen3-8B/vLLM 工作负载。
- 300 条 request traces，覆盖 5 类推理部署/故障设置，2,482 个跨层节点。
- 评估 trace-only、log-only、trace+log 以及多个异常检测和图日志基线。
- 报告压缩率、候选定位、解释质量、模态消融和 tracing overhead。

证据位置：摘要、§3 Method、§4 Experimental Setup、§4.2 Dataset、§4.3 Baselines、§5 Results。

## 5. Limitations

它的对象是 inference infrastructure，不是多 Agent 任务责任。trace 和日志的对齐依赖请求上下文、NVTX 标记和受控部署。其因果上下文主要表示执行依赖，不等同于任务层 Agent responsibility。

## 6. Use for my thesis

TELLER 是你最重要的跨层对照。你可以借鉴它的多模态消融和请求级对齐设计，但应把对象改为 Agent、工具、消息和任务判据，并加入 agent/step/edge 责任标签与反事实干预。论文中必须明确与 GPU inference RCA 的边界。

## 7. Claim–evidence rows

| Claim | Evidence | Status |
|---|---|---|
| trace 与日志联合输入能改善跨层 RCA | §4.3、§5 模态消融 | `VERIFIED` |
| 结构保持压缩能减少 trace 长度 | 摘要、TPE 实验 | `VERIFIED` |
| 同一方法可直接用于多 Agent 责任边 | 论文未研究 | `UNVERIFIED` |
