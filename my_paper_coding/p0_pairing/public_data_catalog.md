# 公开数据与基准候选

更新时间：2026-09-28

用途：为“跨层执行证据—失败归因—可验证诊断”选择外部任务、失败轨迹和标签来源。外部数据先作为适配/验证来源，不直接与本地 AgentSight trace 混合统计。

## 优先级

| 优先级 | 数据/基准 | 可提供什么 | 与本课题的匹配 | 使用边界 |
|---|---|---|---|---|
| P0 | [TraceElephant](https://github.com/huangrubing/TraceElephant-ACL2026) | 220 条标注失败轨迹、责任 Agent、决定性步骤、工具和系统配置，并提供可执行环境 | 最接近方向 01 的 Agent/Step 归因与 replay 需求 | 需要先核对数据下载方式、版本和许可；其轨迹格式不等于 AgentSight schema |
| P0 | [AgentRx](https://huggingface.co/datasets/microsoft/AgentRx) | 失败轨迹、步骤级失败类别、根因失败和失败 Agent；页面标注 CC-BY-4.0 | 可作为根因定位和失败类别适配集 | 当前公开字段是否包含足够的系统层事件，需要下载后逐字段审计 |
| P1 | [MAST](https://github.com/multi-agent-systems-failure-taxonomy/MAST) | 200 条 MAS 执行轨迹、14 类失败本体、专家标注流程 | 用于故障类型映射和 taxonomy 对照 | 主要是失败分类证据，不直接提供 AgentSight 的进程/网络/文件事件 |
| P1 | [Agent Failures](https://github.com/lakmus-ai/agent-failures) | 多模型相同任务的结构化失败/通过记录、失败分类和 judge 证据 | 用于任务结果、失败类型和跨模型稳健性补充 | 更偏通用 agent 任务；必须按其 paired/canonical 规则统计，不能混用原始重复记录 |
| P2 | [SWE-bench Verified](https://www.swebench.com/SWE-bench/guides/datasets/) | 有执行测试判据、`FAIL_TO_PASS`/`PASS_TO_PASS` 和版本化代码任务 | 可作为代码/工具型任务的可执行结果层 | 原生不是多 Agent 失败 trace，需要用本地 Agent 框架重新产生观测轨迹 |
| P2 | [AgentBench](https://github.com/THUDM/AgentBench) | 多环境、多轮 Agent 任务和 dev/test 划分 | 可扩展任务类型和环境覆盖 | 不是专门的责任边/根因数据；部署成本较高，先不作为今天的主数据源 |

## 本轮完成与下一步

本轮已完成：

1. 用本地 marker pilot 验证请求—响应分析器；
2. 读取 TraceElephant 公开仓库的 README 和 evaluator，确认 `trace_metadata.json` / `step_records.json` 字段；
3. 在 `adapt_traceelephant.py` 中实现到本地统一 schema 的适配，并用最小 fixture 通过字段校验。

仍未完成：

4. 下载并审计真实外部失败轨迹的许可、脱敏状态、完整字段和版本；
5. 只有外部数据许可、字段和执行环境都确认后，才纳入 30–50 条 pilot 的训练/测试划分。

## 证据约束

- 外部数据的标签不能直接当作 AgentSight 观测真值；需要记录标签来源、标注协议和可复现版本。
- 没有系统层事件的轨迹只能用于输出/步骤级研究，不能直接支撑跨层边归因。
- 原始 prompt、response 和路径信息先保存在本地脱敏目录，不提交到仓库。
- 本轮对 AgentRx 的目录 API 可见性和原始文件下载分别做了检查；本机直接下载 `tau_retail.jsonl` 返回 HTTP 401，因此没有把 AgentRx 原始数据写入仓库，也没有把它当作已审计数据集。
