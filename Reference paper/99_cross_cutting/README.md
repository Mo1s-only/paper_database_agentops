# 99 Cross-cutting：综合材料来源

本目录不作为独立论文分类，保存跨“观测—归因—诊断—干预—评价”的综合笔记。`新增5篇论文精读笔记.md` 涉及以下论文：

| 论文 | 主存放目录 | 来源 | Venue/级别 |
|---|---|---|---|
| CDC-MAS | `02_failure_attribution/` | [arXiv](https://arxiv.org/abs/2509.08682) | 预印本；本地PDF含AAAI 2026版权，但正式页面待核 |
| EDGE | `02_failure_attribution/` | [arXiv](https://arxiv.org/abs/2609.01360) | 预印本 |
| AgentTrace | `01_agent_observation/` | [arXiv](https://arxiv.org/abs/2603.14688) | ICLR 2026 Agents in the Wild Workshop |
| TraceElephant | `02_failure_attribution/` | [ACL Anthology](https://aclanthology.org/2026.acl-long.912/) | ACL 2026主会长文，顶级会议 |
| MAST | `02_failure_attribution/` | [NeurIPS Proceedings](https://papers.nips.cc/paper_files/paper/2025/hash/b1041e52d3be19f0a9bc491657488e4a-Abstract-Datasets_and_Benchmarks_Track.html) | NeurIPS 2025 Datasets and Benchmarks Track，顶级会议 |

综合笔记中的实验数字和方法结论仍应回到原始PDF核验；本文件只负责来源与发表状态，不替代逐项事实检查。

## 2026-10-22 新增：归因与跨层证据工作

本轮新增 8 篇近期工作来源登记及一份 claim-evidence-gap 笔记：

| 论文 | 主存放目录 | 来源 | 状态/用途 |
|---|---|---|---|
| DCFA | `02_failure_attribution/` | [arXiv:2609.04749](https://arxiv.org/abs/2609.04749) | 预印本；语义 trace + decisive-step / counterfactual-inspired 归因对照 |
| AgentLocate | `02_failure_attribution/` | [arXiv:2607.07989](https://arxiv.org/abs/2607.07989) | 预印本；多 Agent decisive-step 定位强基线候选 |
| VerifyMAS | `02_failure_attribution/` | [arXiv:2605.17467](https://arxiv.org/abs/2605.17467) | 预印本；全轨迹 hypothesis verification 对照 |
| CausalFlow | `02_failure_attribution/` | [arXiv:2605.25338](https://arxiv.org/abs/2605.25338) | 预印本；步骤干预、重放与最小反事实修复对照 |
| TelemetrySuffBench | `02_failure_attribution/` | [arXiv:2608.07899](https://arxiv.org/abs/2608.07899) | 预印本；telemetry sufficiency、origin localization 与 abstention 对照 |
| Agent-Warden | `01_agent_observation/` | [arXiv:2609.38245](https://arxiv.org/abs/2609.38245) | 预印本；Agent process/file eBPF provenance 相邻工作 |
| AgentTelemetry | `01_agent_observation/` | [ACM DOI](https://doi.org/10.1145/3805760.3814931) | AIware '26 正式论文；Agent span taxonomy、框架 adapters 与 fault-detection benchmark |
| ALTEDA | `02_failure_attribution/` | [Elsevier DOI](https://doi.org/10.1016/j.ipm.2026.104768) | IP&M 2026 正式期刊论文；同步应用/网络/系统日志上的多 Agent 威胁检测与归因 |

初读综合与研究增量判断见 `归因方向新增文献与论文增量点_2026-10-22.md`。受当前环境出站网络策略限制，原 PDF 尚未复制到本地；除 ACM/Elsevier 正式论文元数据外，arXiv 条目均只按预印本引用。该缺失已显式记录，待取得原文后补 PDF 与逐页阅读。
