# R15 — TELLER：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文与 Figshare API）；AUTHOR_INPUT_NEEDED（网络策略允许后重试下载）。`

本地论文：[03_diagnosis_localization/TELLER_Non_intrusive_Cross_Layer_RCA_LLM_Inference_ASE2026.pdf](<../../03_diagnosis_localization/TELLER_Non_intrusive_Cross_Layer_RCA_LLM_Inference_ASE2026.pdf>)

## 分类

跨层遥测；LLM inference 根因分析

## 论文实验使用的数据

自建请求级数据：300 条 request traces、2,482 个步骤、约 563 万个跨层节点；覆盖 SGLang 100、Torch FSDP 50、vLLM v0 50、vLLM v1 offline 50、vLLM v1 online 50，含正常与五类故障。

## 获取与本地状态

Figshare 的 TELLER.zip 为 100,739,122 bytes（约 96.1 MiB），符合 100 MiB 阈值；但下载端点在本机返回 HTTP 403，故记录官方 DOI、文件大小和 MD5，不放置空文件。官方 MD5：5e770263ae436a32f377840437f2f7ba。

## 本地数据

- 无。本次未下载的原因见“获取与本地状态”。

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [Figshare/DOI](https://doi.org/10.6084/m9.figshare.33142493.v1)

## 对当前论文的用途

是归因前跨层 schema、request-step-system node 对齐和故障注入比例设计的关键对照。
