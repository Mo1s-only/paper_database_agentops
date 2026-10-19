# Reference paper 实验数据目录

整理日期：2026-10-16

本目录覆盖 `literature_index.md` 中 R01–R30。每篇论文都有独立文件夹和 `README.md`；相同数据只在 `shared_data/` 保存一次，论文文档以相对链接引用。

下载策略：压缩包或可核验本地快照不超过 100 MiB 时下载；大型、受限、未发布或依赖在线环境的数据只记录官方入口。`VERIFIED`、`INFERRED`、`UNVERIFIED`、`AUTHOR_INPUT_NEEDED` 的含义沿用仓库研究规范。

## 归因、失败分类与因果轨迹

- [R03 AgentTrace: Causal Graph Tracing](./R03_AgentTrace/README.md)
- [R05 Which Agent Causes Task Failures and When?](./R05_Who_and_When/README.md)
- [R06 Seeing the Whole Elephant / TraceElephant](./R06_TraceElephant/README.md)
- [R07 Why Do Multi-Agent LLM Systems Fail? / MAST](./R07_MAST/README.md)
- [R08 CDC-MAS](./R08_CDC_MAS/README.md)
- [R09 EDGE: Error Dependency Graph](./R09_EDGE/README.md)
- [R10 Towards Self-Improving Error Diagnosis / ErrorProbe](./R10_ErrorProbe/README.md)
- [R30 OpenRCA 2.0](./R30_OpenRCA_2_0/README.md)

## 通用推理、代码、问答与安全

- [R01 AgentMonitor](./R01_AgentMonitor/README.md)
- [R04 Understanding the Information Propagation Effects in Multi-Agent Systems](./R04_Information_Propagation_Effects/README.md)
- [R11 Watson](./R11_Watson/README.md)
- [R13 Beyond Natural Language](./R13_Beyond_Natural_Language/README.md)
- [R18 AgentDropout](./R18_AgentDropout/README.md)
- [R20 DistServe](./R20_DistServe/README.md)
- [R21 AgentEval](./R21_AgentEval/README.md)

## 交互式 Agent、工具与多智能体环境

- [R14 Tools Fail](./R14_Tools_Fail/README.md)
- [R19 Breaking Agents](./R19_Breaking_Agents/README.md)
- [R22 AgentBench](./R22_AgentBench/README.md)
- [R23 AgentBoard](./R23_AgentBoard/README.md)
- [R24 τ-bench](./R24_TauBench/README.md)
- [R25 LLMArena](./R25_LLMArena/README.md)
- [R26 MultiAgentBench](./R26_MultiAgentBench/README.md)
- [R27 DREAM](./R27_DREAM/README.md)

## 系统、微服务与 LLM Serving 遥测

- [R02 AgentSight](./R02_AgentSight/README.md)
- [R12 eInfer](./R12_eInfer/README.md)
- [R15 TELLER](./R15_TELLER/README.md)
- [R16 GALA](./R16_GALA/README.md)
- [R17 ReLog](./R17_ReLog/README.md)
- [R28 RCACopilot](./R28_RCACopilot/README.md)
- [R29 OpenRCA](./R29_OpenRCA/README.md)
- [R30 OpenRCA 2.0](./R30_OpenRCA_2_0/README.md)


## 已保存的本地数据快照

| 名称 | 文件数 | 大小 | SHA-256/目录树 SHA-256 | 关联论文 |
|---|---:|---:|---|---|
| [AgentTrace_ICLR2026_data](./shared_data/AgentTrace_ICLR2026_data) | 3521 | 21.40 MiB | `8cffc374aa5b09d6c4b704b14ac52f3201dfe35baeadb56928ce8495f9ebc4df` | R03 |
| [WhoAndWhen_184](./shared_data/WhoAndWhen_184) | 184 | 6.49 MiB | `07c64ea9b19e524fd52cdc3164263ebdb6fa822a0513f8ec9a44640810ab9f05` | R05, R08, R10 |
| [AutoForm_exact_subsets](./shared_data/AutoForm_exact_subsets) | 16 | 21.12 MiB | `22e30dfedb35c3efc38b5363ae63d26cdb13fa72a0d9638ce0be98037290ddc2` | R13 |
| [EIB_selected_datasets](./shared_data/EIB_selected_datasets) | 6 | 0.92 MiB | `55fc642e4837c9879c0db9000907d1873f9e14518539e181c6eaa8318a4a04fa` | R04, R18 |
| [AgentBench_data](./shared_data/AgentBench_data) | 125 | 30.56 MiB | `d9cf6e65daa3f0054370d02d83451e6ce4815f88131433490e7bef18956782c9` | R22 |
| [TauBench_package](./shared_data/TauBench_package) | 100 | 8.42 MiB | `1894e4a8924e34b78b3f33b867c3d3e21a138f6ddb74a9822db192ef0e4fbf53` | R24 |
| [GALA_annotation](./shared_data/GALA_annotation) | 3 | 0.21 MiB | `14c9946e060f3e6f4b41329cc9e3dedc703efe3fb5c76e30104e690e096f1a51` | R16 |
| [TRAIL_benchmarking_148_traces.zip](./shared_data/TRAIL_benchmarking_148_traces.zip) | 1 | 30.00 MiB | `518875332ffb616aa7d56c369821b30399531e2549049a9563f708c6a4c94ddc` | R08, R09 |
| [MultiAgentBench_task_configs](./shared_data/MultiAgentBench_task_configs) | 1219 | 7.75 MiB | `80e4104e32554435173232c52743c7bba7098fe4f04946f6378671677fb1c68f` | R26 |

详细来源、提交版本和机器可读校验信息见 [`manifest.json`](./manifest.json)。目录树摘要按“相对路径 + 每文件 SHA-256”排序计算，可检测内容或文件名变化。

## 尚未本地下载但已核验的数据

- TraceElephant：约 597 MB，超过阈值。
- MAST 完整集：约 200 MB，超过阈值；2.66 MB 人工子集因本机 Hugging Face 连接超时待重试。
- TELLER：约 96.1 MiB，下载端点返回 HTTP 403，已保存 DOI、官方大小和 MD5。
- ReLog：约 143.2 MiB，超过阈值。
- OpenRCA：约 68–68.5 GB，超过阈值。
- DREAM/LiveResearchBench：需要接受数据访问条款。
- OpenRCA 2.0：论文描述的数据 artifact 尚未找到公开下载页。

## 下一道研究关口

先用本地 Who&When、TRAIL、AgentTrace 三类数据建立统一字段映射：`run/session → agent → step/span → relation → label/evidence`。只有映射完成后，才能比较现有跨层观测 schema 对节点、边和路径真值的覆盖率。
