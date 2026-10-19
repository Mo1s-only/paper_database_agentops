# R07 — Why Do Multi-Agent LLM Systems Fail? / MAST：实验数据说明

整理日期：2026-10-16  
证据状态：`VERIFIED（论文和官方数据页）；AUTHOR_INPUT_NEEDED（是否允许以后获取更新版并冻结快照）。`

本地论文：[02_failure_attribution/MAST_Why_Do_Multi_Agent_LLM_Systems_Fail.pdf](<../../02_failure_attribution/MAST_Why_Do_Multi_Agent_LLM_Systems_Fail.pdf>)

## 分类

失败分类法；人工/自动标注轨迹

## 论文实验使用的数据

当前官方发布页列出 1,642 条轨迹、7 个框架、8 个基准和 5 个模型。完整 MAD_full_dataset.json 约 200 MB；人工标注子集 MAD_human_labelled_dataset.json 约 2.66 MB。

## 获取与本地状态

完整集超过阈值，保留链接。人工子集符合下载阈值，但本机访问 Hugging Face 于 2026-10-16 连续超时，未创建伪数据文件，待网络恢复后重试。论文正文与当前发布页的人类标注条数存在版本差异，引用时应注明版本。

## 本地数据

- 无。本次未下载的原因见“获取与本地状态”。

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

- [官方仓库](https://github.com/multi-agent-systems-failure-taxonomy/MAST)
- [数据集](https://huggingface.co/datasets/mcemri/MAST-Data/tree/main)

## 对当前论文的用途

用于建立失败类型标签体系和人类一致性评估；不能把当前发布页统计无条件回填为论文投稿时版本。
