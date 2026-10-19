from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SHARED = ROOT / "shared_data"
RETRIEVED_AT = "2026-10-16"


def load_paper_files() -> dict[str, str]:
    index = (ROOT.parent / "literature_index.md").read_text(encoding="utf-8")
    result = {}
    for line in index.splitlines():
        match = re.match(r"\| (R\d\d) \|.*?`([^`]+\.pdf)` \|$", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


PAPER_FILES = load_paper_files()


PAPERS = [
    {
        "id": "R01", "slug": "AgentMonitor", "title": "AgentMonitor",
        "category": "通用推理/代码/安全；多智能体性能预测",
        "datasets": "HumanEval、MMLU、GSM8K，以及从 MINT 采样的代码/推理/数学任务；安全实验使用 BeaverTails、MaliciousInstruct、AdvBench，各采样 100 条。",
        "access": "这些是多个上游公开基准的组合。论文仓库公开，但未发现与论文抽样完全一致、带固定样本 ID 的统一数据包，因此没有重复下载全部通用基准。",
        "links": [("论文代码", "https://github.com/chanchimin/AgentMonitor"), ("HumanEval", "https://github.com/openai/human-eval"), ("GSM8K", "https://github.com/openai/grade-school-math"), ("BeaverTails", "https://huggingface.co/datasets/PKU-Alignment/BeaverTails")],
        "local": [], "evidence": "VERIFIED（论文实验设置与官方仓库）；论文所用精确抽样 ID 未公开。",
        "use": "适合作为语义任务成功率与安全违规率基准；若复现，必须固定抽样 ID、随机种子和版本。",
    },
    {
        "id": "R02", "slug": "AgentSight", "title": "AgentSight",
        "category": "真实软件代理工作流；系统级观测",
        "datasets": "没有静态问答数据集。实验在教程代码仓库上运行 Claude Code 的三个真实工作流：仓库理解（/init）、bpftrace 代码生成、仓库编译；每个工作流重复 3 次。",
        "access": "数据由真实运行生成，核心输入是代码仓库、提示和系统环境。要复现应保存仓库提交、模型版本、命令、运行轨迹与机器配置。",
        "links": [("论文代码", "https://github.com/eunomia-bpf/agentsight")],
        "local": [], "evidence": "VERIFIED（论文实验章节）；INFERRED（归类为运行时工作负载而非静态数据集）。",
        "use": "直接对应当前论文的跨层事件采集，可用同一任务多次运行形成时钟对齐与进程身份映射的重复性数据。",
    },
    {
        "id": "R03", "slug": "AgentTrace", "title": "AgentTrace: Causal Graph Tracing",
        "category": "合成多智能体轨迹；因果图与根因节点标注",
        "datasets": "论文构造 10 个领域、550 个场景的合成基准。官方 ICLR 2026 workshop artifact 的 data 目录还包含场景、真值和部分结果文件，因此本地文件数会多于 550。",
        "access": "官方仓库标签 iclr2026-aiwild-camera-ready，固定提交 323fc63。已下载该标签的 data 目录。",
        "links": [("官方仓库", "https://github.com/GeoffreyWang1117/AgentTrace")],
        "local": ["AgentTrace_ICLR2026_data"], "evidence": "VERIFIED（论文、官方标签和本地文件）。",
        "use": "可用于验证事件到因果图的结构转换、根因节点排序和场景级可重放；不能把仓库中的模型输出当作独立人工真值。",
    },
    {
        "id": "R04", "slug": "Information_Propagation_Effects", "title": "Understanding the Information Propagation Effects in Multi-Agent Systems",
        "category": "推理/数学/代码；通信拓扑与错误传播",
        "datasets": "MMLU、GSM8K、AQuA、MultiArith、SVAMP、HumanEval 六个公开基准。",
        "access": "官方实现现位于 EIB_learner。仓库 datasets 目录只内置/提供部分数据与下载脚本，并不等同于六个基准的完整统一镜像。已保存其中可直接取得的 6 个文件。",
        "links": [("官方仓库", "https://github.com/se7esx/EIB_learner")],
        "local": ["EIB_selected_datasets"], "evidence": "VERIFIED（论文和官方仓库）。",
        "use": "可作为通信边、拓扑和错误信息传播实验的语义任务输入；复现时需补齐未内置的上游数据。",
    },
    {
        "id": "R05", "slug": "Who_and_When", "title": "Which Agent Causes Task Failures and When?",
        "category": "多智能体失败轨迹；Agent级与步骤级归因",
        "datasets": "Who&When 共 184 条失败轨迹，来自 127 个 agentic systems。Algorithm-Generated 部分基于 CaptainAgent 与 GAIA/AssistantBench；Hand-Crafted 部分基于 Magentic-One 与 AssistantBench，并加入 30 个 GAIA 任务。",
        "access": "官方仓库同时给出数据目录与 Hugging Face 页面。已下载仓库中的 184 个数据文件，固定提交 f4d2b6d。",
        "links": [("官方仓库", "https://github.com/ag2ai/Agents_Failure_Attribution"), ("Hugging Face", "https://huggingface.co/datasets/Kevin355/Who_and_When")],
        "local": ["WhoAndWhen_184"], "evidence": "VERIFIED（论文、官方仓库和本地文件）。",
        "use": "可直接作为归因前数据模式设计的参考：保存 agent、step、失败标签及证据位置，并区分自动生成与人工构造轨迹。",
    },
    {
        "id": "R06", "slug": "TraceElephant", "title": "Seeing the Whole Elephant / TraceElephant",
        "category": "全轨迹失败归因；可复现实验环境",
        "datasets": "共 380 次执行、220 条失败轨迹：Captain-Agent/GAIA 126/73、Captain-Agent/AssistantBench 21/12、Magentic-One/GAIA 119/74、Magentic-One/AssistantBench 30/17、SWE-Agent/SWE-Bench 84/44（执行数/失败数）。",
        "access": "官方 Hugging Face 数据包约 597 MB，超过本项目 100 MiB 本地阈值，因此只保留链接。许可证为 CC BY 4.0。",
        "links": [("官方仓库", "https://github.com/TraceElephant/TraceElephant"), ("数据集", "https://huggingface.co/datasets/TraceElephant/TraceElephant/tree/main")],
        "local": [], "evidence": "VERIFIED（论文与官方数据页）。",
        "use": "适合后续检验“完整观测是否提高归因”，但下载前需准备约 0.6 GB 空间并固定数据版本。",
    },
    {
        "id": "R07", "slug": "MAST", "title": "Why Do Multi-Agent LLM Systems Fail? / MAST",
        "category": "失败分类法；人工/自动标注轨迹",
        "datasets": "当前官方发布页列出 1,642 条轨迹、7 个框架、8 个基准和 5 个模型。完整 MAD_full_dataset.json 约 200 MB；人工标注子集 MAD_human_labelled_dataset.json 约 2.66 MB。",
        "access": "完整集超过阈值，保留链接。人工子集符合下载阈值，但本机访问 Hugging Face 于 2026-10-16 连续超时，未创建伪数据文件，待网络恢复后重试。论文正文与当前发布页的人类标注条数存在版本差异，引用时应注明版本。",
        "links": [("官方仓库", "https://github.com/multi-agent-systems-failure-taxonomy/MAST"), ("数据集", "https://huggingface.co/datasets/mcemri/MAST-Data/tree/main")],
        "local": [], "evidence": "VERIFIED（论文和官方数据页）；AUTHOR_INPUT_NEEDED（是否允许以后获取更新版并冻结快照）。",
        "use": "用于建立失败类型标签体系和人类一致性评估；不能把当前发布页统计无条件回填为论文投稿时版本。",
    },
    {
        "id": "R08", "slug": "CDC_MAS", "title": "CDC-MAS",
        "category": "因果归因；性能反转、Shapley值和因果发现",
        "datasets": "论文在 Who&When 与 TRAIL 两类互补数据上评估：前者提供 Agent/步骤失败归因，后者提供 span 级多错误标注。",
        "access": "两个数据源均为公开数据。已保存 Who&When 数据目录和 TRAIL benchmarking 压缩包；TRAIL 本地包约 30 MB。",
        "links": [("Who&When", "https://github.com/ag2ai/Agents_Failure_Attribution"), ("TRAIL", "https://github.com/patronus-ai/trail-benchmark")],
        "local": ["WhoAndWhen_184", "TRAIL_benchmarking_148_traces.zip"], "evidence": "VERIFIED（论文实验设置与官方数据源）。",
        "use": "适合比较单根因与多错误场景的数据 schema，并为后续 Agent/step/edge 三层归因准备标签映射。",
    },
    {
        "id": "R09", "slug": "EDGE", "title": "EDGE: Error Dependency Graph",
        "category": "多错误轨迹；错误依赖边与反事实重放",
        "datasets": "TRAIL 的 148 条轨迹（官方说明含 841 个错误）以及 MAST/MAD 中 393 条 AutoGen 轨迹。",
        "access": "TRAIL 已下载为 30 MB 压缩包。MAST 完整文件约 200 MB，只保留官方链接；393 条子集需按论文筛选条件从完整集重建。",
        "links": [("EDGE 官方仓库", "https://github.com/JuneHou/EDGE"), ("TRAIL", "https://github.com/patronus-ai/trail-benchmark"), ("MAST 数据", "https://huggingface.co/datasets/mcemri/MAST-Data/tree/main")],
        "local": ["TRAIL_benchmarking_148_traces.zip"], "evidence": "VERIFIED（论文和官方数据源）。",
        "use": "是当前论文未来做边级传播归因最相关的数据；下一步需把 TRAIL span 标注映射到本项目事件和关系 schema。",
    },
    {
        "id": "R10", "slug": "ErrorProbe", "title": "Towards Self-Improving Error Diagnosis / ErrorProbe",
        "category": "代码代理轨迹；错误诊断和验证记忆",
        "datasets": "实验使用 TracerTraj 的代码生成子集，以及 Who&When-Algorithm-Generated 和 Who&When-Hand-Crafted 两个子集。论文将 TracerTraj 描述为来自 AgenTracer 的约 2.5K 轨迹资源。",
        "access": "Who&When 已本地保存。当前未定位到可核验的 TracerTraj 官方独立下载页，因此仅记录论文中的使用事实，不提供猜测链接。",
        "links": [("Who&When", "https://github.com/ag2ai/Agents_Failure_Attribution")],
        "local": ["WhoAndWhen_184"], "evidence": "VERIFIED（论文对数据集的描述）；UNVERIFIED（TracerTraj 独立公开下载地址）。",
        "use": "可用于设计反向错误候选检索与执行验证；在 TracerTraj 来源确认前，不应声称完成该基准复现。",
    },
    {
        "id": "R11", "slug": "Watson", "title": "Watson",
        "category": "推理与软件修复；隐式认知轨迹诊断",
        "datasets": "MMLU 全集 14,042 题，论文从中构造三个各 374 题的子集；软件工程实验使用 SWE-bench Lite 300 个 issue，并运行 AutoCodeRover 和 OpenHands。",
        "access": "基准公开但模型运行轨迹体量和依赖较大，未重复镜像。精确 374 题子集需要论文代码或采样配置才能保证一致。",
        "links": [("MMLU", "https://github.com/hendrycks/test"), ("SWE-bench", "https://github.com/SWE-bench/SWE-bench")],
        "local": [], "evidence": "VERIFIED（论文实验章节）；精确 MMLU 子集 ID 未在本地材料中确认。",
        "use": "可借鉴“恢复推理轨迹后再检查”的诊断思路，数据准备必须同时固定 agent 实现和仓库镜像。",
    },
    {
        "id": "R12", "slug": "eInfer", "title": "eInfer",
        "category": "LLM 推理系统负载；eBPF 跨层追踪",
        "datasets": "没有命名的静态数据集。实验由 Qwen3-0.6B、Llama3-8B、Llama2-13B、Llama3-70B 等模型的推理工作负载生成系统事件。",
        "access": "复现对象是模型、推理框架、硬件和请求负载的组合；应保存版本、请求生成参数、并发度、GPU/CPU 环境与 eBPF 原始事件。",
        "links": [], "local": [], "evidence": "VERIFIED（论文实验设置）；INFERRED（归类为工作负载生成数据）。",
        "use": "与当前 PID namespace、进程/线程身份和纳秒时钟对齐工作直接相关，可作为系统层实验设计模板。",
    },
    {
        "id": "R13", "slug": "Beyond_Natural_Language", "title": "Beyond Natural Language",
        "category": "推理与多智能体通信格式",
        "datasets": "单体推理使用 Logic Grid、Coin Flip、Information Essentiality、Minute Mysteries QA、AQuA；多智能体通信使用 HotpotQA、WikiHop、NarrativeQA。",
        "access": "官方 AutoForm 仓库提供论文所用 data 目录。已下载 16 个文件、约 21 MB，固定提交 8df9450。",
        "links": [("官方仓库", "https://github.com/thunlp/AutoForm")],
        "local": ["AutoForm_exact_subsets"], "evidence": "VERIFIED（论文、官方仓库和本地文件）。",
        "use": "可用于分析消息格式、token 成本和通信效率；不应把格式效率结果直接解释为故障归因准确率。",
    },
    {
        "id": "R14", "slug": "Tools_Fail", "title": "Tools Fail",
        "category": "工具静默错误；动作规划与目标检测",
        "datasets": "论文构造计算器工具错误任务，并从 ALFRED 派生 action planner 490 条、object detector 214 条实验实例。",
        "access": "论文指向的 tools-fail 官方仓库当前仅有说明文件，未发现可下载的数据文件，因此只保留仓库链接。",
        "links": [("官方仓库", "https://github.com/jiminsun/tools-fail"), ("ALFRED", "https://github.com/askforalfred/alfred")],
        "local": [], "evidence": "VERIFIED（论文中的规模）；UNVERIFIED（论文精确派生实例未在当前仓库发布）。",
        "use": "可作为工具返回值正确但语义错误的故障模型来源；本地实验应自行保存注入规则与实例 ID。",
    },
    {
        "id": "R15", "slug": "TELLER", "title": "TELLER",
        "category": "跨层遥测；LLM inference 根因分析",
        "datasets": "自建请求级数据：300 条 request traces、2,482 个步骤、约 563 万个跨层节点；覆盖 SGLang 100、Torch FSDP 50、vLLM v0 50、vLLM v1 offline 50、vLLM v1 online 50，含正常与五类故障。",
        "access": "Figshare 的 TELLER.zip 为 100,739,122 bytes（约 96.1 MiB），符合 100 MiB 阈值；但下载端点在本机返回 HTTP 403，故记录官方 DOI、文件大小和 MD5，不放置空文件。官方 MD5：5e770263ae436a32f377840437f2f7ba。",
        "links": [("Figshare/DOI", "https://doi.org/10.6084/m9.figshare.33142493.v1")],
        "local": [], "evidence": "VERIFIED（论文与 Figshare API）；AUTHOR_INPUT_NEEDED（网络策略允许后重试下载）。",
        "use": "是归因前跨层 schema、request-step-system node 对齐和故障注入比例设计的关键对照。",
    },
    {
        "id": "R16", "slug": "GALA", "title": "GALA",
        "category": "微服务多模态遥测；图增强根因分析",
        "datasets": "OnlineBoutique 90 个注入故障场景（17 服务中的 5 个服务，6 类故障，各 3 次）；TrainTicket 90 个场景（69 个微服务）；另评估 AegisLab 100 个采样故障、25 类故障。",
        "access": "官方仓库 data/annotated_dataset.csv 已下载，本地 data 目录约 0.21 MB，固定提交 24d1329。该文件是公开标注切片，不等于论文全部原始遥测。",
        "links": [("官方仓库", "https://github.com/EvanTian233/GALA-for-RCA")],
        "local": ["GALA_annotation"], "evidence": "VERIFIED（论文、官方仓库和本地文件）。",
        "use": "适合参考服务依赖图与 metrics/logs/traces 的融合方式；论文规模不能从这一小型 CSV 反推。",
    },
    {
        "id": "R17", "slug": "ReLog", "title": "ReLog",
        "category": "软件缺陷；执行感知日志与调试",
        "datasets": "基于 Defects4J：direct debugging 311 个样本、16 个项目；indirect debugging 225 个样本、15 个项目。",
        "access": "Figshare replication.zip 为 150,136,718 bytes（约 143.2 MiB），超过本项目阈值，仅保存 DOI。官方 MD5：82790e3d9ba10210b626d340f2eae90d。",
        "links": [("Figshare/DOI", "https://doi.org/10.6084/m9.figshare.31866106")],
        "local": [], "evidence": "VERIFIED（论文与 Figshare API）。",
        "use": "可以支持“观测数据是否提升下游定位/修复”的效用评价，但任务对象是程序缺陷而非多智能体责任。",
    },
    {
        "id": "R18", "slug": "AgentDropout", "title": "AgentDropout",
        "category": "推理/数学/代码；拓扑剪枝和成本",
        "datasets": "MMLU、GSM8K、AQuA、MultiArith、SVAMP、HumanEval，与信息传播类研究有较强重叠。",
        "access": "官方仓库主要提供数据加载脚本，没有统一内置全部数据。为避免重复，已下载的 EIB 小型数据只在 shared_data 保存一份。",
        "links": [("官方仓库", "https://github.com/wangzx1219/AgentDropout")],
        "local": ["EIB_selected_datasets"], "evidence": "VERIFIED（论文与官方仓库）；本地包只覆盖其中部分基准。",
        "use": "可用于拓扑干预与 token/性能权衡；复现要记录每次删除的 Agent 和通信边。",
    },
    {
        "id": "R19", "slug": "Breaking_Agents", "title": "Breaking Agents",
        "category": "Agent 故障放大与攻击；工具环境",
        "datasets": "Agent Emulator 构造 144 个测试用例，覆盖 36 个 toolkits、300 余个工具；另含 Gmail Agent、CSV Agent 及多智能体案例。",
        "access": "这是运行时生成的攻击/交互用例集合。当前本地证据未确认独立公开静态数据包，因此保留论文定义，不伪造下载地址。",
        "links": [], "local": [], "evidence": "VERIFIED（论文中的实验规模）；UNVERIFIED（独立数据发布位置）。",
        "use": "可为循环调用、任务偏离和故障放大设计压力测试，并把攻击提示、工具调用和终止条件写入轨迹。",
    },
    {
        "id": "R20", "slug": "DistServe", "title": "DistServe",
        "category": "LLM 服务负载；SLO 与 goodput",
        "datasets": "使用 ShareGPT 聊天负载、HumanEval 代码补全、LongBench 摘要任务；由于原数据没有请求时间戳，论文用 Poisson 到达过程合成请求到达。",
        "access": "原始语料和系统复现实验依赖较多，未本地镜像。官方代码提供负载生成和服务实现入口。",
        "links": [("官方仓库", "https://github.com/LLMServe/DistServe")],
        "local": [], "evidence": "VERIFIED（论文实验设置与官方仓库）。",
        "use": "用于设计 TTFT、TPOT、goodput 和并发负载维度；合成到达参数必须与数据内容分开记录。",
    },
    {
        "id": "R21", "slug": "AgentEval", "title": "AgentEval",
        "category": "任务效用评价；数学与具身环境",
        "datasets": "MATH 共 12,500 题，论文选取 120 个 level-5 难题；另使用 ALFWorld household task。",
        "access": "官方仓库提供评测实现和部分运行产物；精确 120 题选择与 ALFWorld 环境依赖需要按代码配置重建，未重复下载完整上游资源。",
        "links": [("官方仓库", "https://github.com/Narabzad/AgentEval"), ("MATH", "https://github.com/hendrycks/math"), ("ALFWorld", "https://github.com/alfworld/alfworld")],
        "local": [], "evidence": "VERIFIED（论文与官方仓库）。",
        "use": "可参考自动生成评价准则，但需单独验证 LLM judge 与人工评分的一致性。",
    },
    {
        "id": "R22", "slug": "AgentBench", "title": "AgentBench",
        "category": "通用交互式 Agent 环境",
        "datasets": "8 个环境：Operating System、Database、Knowledge Graph、Digital Card Game、Lateral Thinking Puzzle、House Holding（ALFWorld）、Web Shopping（WebShop）、Web Browsing（Mind2Web）。论文开发/测试集合计 269/1,014 个任务。",
        "access": "官方仓库 data 目录已下载：125 个文件、约 30.6 MB，固定提交 d1e4a10。部分环境仍需数据库、容器或外部资源，本地 data 不是一键可运行的完整环境镜像。",
        "links": [("官方仓库", "https://github.com/THUDM/AgentBench")],
        "local": ["AgentBench_data"], "evidence": "VERIFIED（论文、官方仓库和本地文件）。",
        "use": "可提供多类型 agent 任务，但若用于归因前观测实验，应先选一个环境冻结依赖并记录每轮动作/观察。",
    },
    {
        "id": "R23", "slug": "AgentBoard", "title": "AgentBoard",
        "category": "过程级 Agent 评测；九类环境任务",
        "datasets": "9 个任务分四类：Embodied AI（AlfWorld、ScienceWorld、BabyAI）、Game（Jericho、PDDL）、Web（WebShop、WebArena）、Tool（Tool-Query、Tool-Operation）。",
        "access": "官方数据以 data.tar.gz 发布，并包含多种环境附加资源；Tool 与 Web 任务还依赖 API 或网络。Hugging Face 从本机超时且完整包大小未可靠取得，因此只保留官方链接。",
        "links": [("官方仓库", "https://github.com/hkust-nlp/AgentBoard"), ("官方数据", "https://huggingface.co/datasets/hkust-nlp/agentboard")],
        "local": [], "evidence": "VERIFIED（官方 README 和论文）；UNVERIFIED（本次未取得压缩包大小）。",
        "use": "过程进展率比最终成功率更适合观测实验；复现时应区分静态 test.jsonl 与外部环境资源。",
    },
    {
        "id": "R24", "slug": "TauBench", "title": "τ-bench",
        "category": "工具代理可靠性；对话用户模拟与数据库状态",
        "datasets": "Retail 和 Airline 两个领域，包含 policy、工具、任务、初始数据库以及用户模拟器。核心评价检查最终数据库状态和 pass^k。",
        "access": "官方仓库 tau_bench 包已下载：约 8.4 MB、100 个文件，固定提交 59a200c。运行仍需要模型/API 配置。",
        "links": [("官方仓库", "https://github.com/sierra-research/tau-bench")],
        "local": ["TauBench_package"], "evidence": "VERIFIED（论文、官方仓库和本地文件）。",
        "use": "很适合做重复运行可靠性和状态变更审计；应保存任务输入、工具调用、数据库 diff 与每次运行结果。",
    },
    {
        "id": "R25", "slug": "LLMArena", "title": "LLMArena",
        "category": "动态多智能体博弈环境",
        "datasets": "以动态竞争/协作游戏环境生成交互，不是固定静态问答集；评价对手建模、合作与策略适应。",
        "access": "官方仓库提供环境和配置，实际轨迹由运行生成。未复制整个环境仓库，避免将代码依赖误标为数据集。",
        "links": [("官方仓库", "https://github.com/THU-BPM/LLMArena")],
        "local": [], "evidence": "VERIFIED（论文与官方仓库）；INFERRED（归类为环境生成数据）。",
        "use": "可用来补充动态交互下的拓扑与通信观测，但与静态根因标签数据应分开管理。",
    },
    {
        "id": "R26", "slug": "MultiAgentBench", "title": "MultiAgentBench",
        "category": "多智能体协作/竞争；里程碑 KPI",
        "datasets": "覆盖 ResearchTown、Bargaining、Werewolf、数据库错误分析、Coding、Minecraft 等场景。论文为任务构造测试用例；ResearchTown 使用 100 篇 ML/AI 论文，按 33/34/33 个易/中/难任务组织。",
        "access": "官方 MARBLE 仓库提供大量任务配置。已抽取 coding、database、werewolf、minecraft 等可直接核验的配置与小型映射文件，共 1,219 个文件、约 7.75 MB；它们是配置快照，不包含所有运行依赖和 ResearchTown 论文全文。",
        "links": [("官方仓库", "https://github.com/ulab-uiuc/MARBLE")],
        "local": ["MultiAgentBench_task_configs"], "evidence": "VERIFIED（论文、官方仓库和本地配置）。",
        "use": "动态里程碑 KPI 和多种拓扑适合验证当前 trace schema 是否能跨协作模式工作。",
    },
    {
        "id": "R27", "slug": "DREAM", "title": "DREAM",
        "category": "深度研究报告；自适应评价",
        "datasets": "主要使用 DeepResearch Bench：6 个 agent、50 个查询、300 份报告；另构造 20 个时效查询×3 个截止时间、10 个复杂查询的 20 份配对报告，以及 15 组对抗事实声明。",
        "access": "论文关联的 LiveResearchBench 当前需要接受 Hugging Face 访问条款。文件页面显示规模较小，但访问受限，因此只保留链接，不绕过授权。",
        "links": [("LiveResearchBench", "https://huggingface.co/datasets/Salesforce/LiveResearchBench")],
        "local": [], "evidence": "VERIFIED（论文与官方数据页）；AUTHOR_INPUT_NEEDED（接受数据条款后方可下载）。",
        "use": "适合借鉴时效性、事实性和覆盖率评价；与运行时故障归因的标签语义不同。",
    },
    {
        "id": "R28", "slug": "RCACopilot", "title": "RCACopilot",
        "category": "工业事故；多源证据与根因类别",
        "datasets": "Microsoft Transport 一年内 653 个 incidents，按 75%/25% 划分训练/测试，由专家标注根因类别，并结合告警、日志和处理记录。",
        "access": "数据包含企业内部事故信息，论文未提供公开下载。这里只记录规模和数据类型，不创建替代或合成文件。",
        "links": [], "local": [], "evidence": "VERIFIED（论文）；数据访问状态为非公开。",
        "use": "可借鉴 incident handler 的证据收集流程和弱分类任务定义，不能作为可复现公开基准。",
    },
    {
        "id": "R29", "slug": "OpenRCA", "title": "OpenRCA",
        "category": "微服务 RCA；多模态遥测",
        "datasets": "335 个校准后的故障案例、约 68–68.5 GB 遥测，来自三个 AIOps challenge 系统（电信数据库、银行、在线市场）。论文描述原始 1,753 条，经平衡为 412 条，再校准为 335 条。",
        "access": "远超本项目下载阈值，只保留 Microsoft 官方仓库链接。仓库当前主提交核验为 c121a48。",
        "links": [("官方仓库", "https://github.com/microsoft/OpenRCA")],
        "local": [], "evidence": "VERIFIED（论文和官方仓库）。",
        "use": "是程序化证据查询和结构化 RCA 输出的重要基准；下载前应单独规划约 70 GB 存储与预处理缓存。",
    },
    {
        "id": "R30", "slug": "OpenRCA_2_0", "title": "OpenRCA 2.0",
        "category": "因果过程监督；节点/边/路径真值",
        "datasets": "从 8,137 次故障注入运行中精选 500 个实例，覆盖 TrainTicket、OpenTelemetry Demo、DeathStarBench Hotel Reservation 三个系统和 27 类 chaos primary kind；每例包含 traces、metrics、logs 与因果图。",
        "access": "论文说明匿名预览/完整包随投稿提供，并计划接受后公开 PAVE artifact；截至本次整理未找到可核验的公开数据仓库。仅记录论文链接和三个上游系统。",
        "links": [("论文", "https://arxiv.org/abs/2606.27154"), ("TrainTicket", "https://github.com/FudanSELab/train-ticket"), ("OpenTelemetry Demo", "https://github.com/open-telemetry/opentelemetry-demo"), ("DeathStarBench", "https://github.com/delimitrou/DeathStarBench")],
        "local": [], "evidence": "VERIFIED（论文数据构造描述）；UNVERIFIED（公开数据 artifact 尚未找到）。",
        "use": "其 root/node/edge/path/evidence-query 层次可直接作为后续归因数据协议的对齐目标。",
    },
]


SOURCES = {
    "AgentTrace_ICLR2026_data": {"source": "https://github.com/GeoffreyWang1117/AgentTrace", "ref": "iclr2026-aiwild-camera-ready / 323fc63", "papers": ["R03"]},
    "WhoAndWhen_184": {"source": "https://github.com/ag2ai/Agents_Failure_Attribution", "ref": "main / f4d2b6d", "papers": ["R05", "R08", "R10"]},
    "AutoForm_exact_subsets": {"source": "https://github.com/thunlp/AutoForm", "ref": "main / 8df9450", "papers": ["R13"]},
    "EIB_selected_datasets": {"source": "https://github.com/se7esx/EIB_learner", "ref": "main / f34d42f", "papers": ["R04", "R18"]},
    "AgentBench_data": {"source": "https://github.com/THUDM/AgentBench", "ref": "main / d1e4a10", "papers": ["R22"]},
    "TauBench_package": {"source": "https://github.com/sierra-research/tau-bench", "ref": "main / 59a200c", "papers": ["R24"]},
    "GALA_annotation": {"source": "https://github.com/EvanTian233/GALA-for-RCA", "ref": "main / 24d1329", "papers": ["R16"]},
    "TRAIL_benchmarking_148_traces.zip": {"source": "https://github.com/patronus-ai/trail-benchmark", "ref": "main / 0ffbed9", "papers": ["R08", "R09"]},
    "MultiAgentBench_task_configs": {"source": "https://github.com/ulab-uiuc/MARBLE", "ref": "main / 8d60fa1", "papers": ["R26"]},
}


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def describe_path(path: Path) -> dict:
    if path.is_file():
        return {"file_count": 1, "bytes": path.stat().st_size, "sha256": file_hash(path)}
    files = sorted(p for p in path.rglob("*") if p.is_file())
    tree = hashlib.sha256()
    total = 0
    for file in files:
        rel = file.relative_to(path).as_posix()
        digest = file_hash(file)
        total += file.stat().st_size
        tree.update(rel.encode("utf-8"))
        tree.update(b"\0")
        tree.update(digest.encode("ascii"))
        tree.update(b"\n")
    return {"file_count": len(files), "bytes": total, "sha256_tree": tree.hexdigest()}


def write_paper(paper: dict) -> None:
    folder = ROOT / f"{paper['id']}_{paper['slug']}"
    folder.mkdir(parents=True, exist_ok=True)
    links = "\n".join(f"- [{name}]({url})" for name, url in paper["links"]) or "- 无已核验的独立公开数据链接；以本地论文为证据。"
    if paper["local"]:
        local = "\n".join(f"- [`shared_data/{name}`](../shared_data/{name})" for name in paper["local"])
    else:
        local = "- 无。本次未下载的原因见“获取与本地状态”。"
    paper_file = PAPER_FILES.get(paper["id"])
    if not paper_file:
        raise KeyError(f"Paper path missing from literature_index.md: {paper['id']}")
    paper_target = "../../" + paper_file.replace("\\", "/")
    text = f"""# {paper['id']} — {paper['title']}：实验数据说明

整理日期：{RETRIEVED_AT}  
证据状态：`{paper['evidence']}`

本地论文：[{paper_file}](<{paper_target}>)

## 分类

{paper['category']}

## 论文实验使用的数据

{paper['datasets']}

## 获取与本地状态

{paper['access']}

## 本地数据

{local}

共享目录用于去重；本文件仍单独说明该论文实际使用的数据及其边界。

## 官方入口

{links}

## 对当前论文的用途

{paper['use']}
"""
    (folder / "README.md").write_text(text, encoding="utf-8")


def build_index(manifest: list[dict]) -> None:
    groups = {
        "归因、失败分类与因果轨迹": ["R03", "R05", "R06", "R07", "R08", "R09", "R10", "R30"],
        "通用推理、代码、问答与安全": ["R01", "R04", "R11", "R13", "R18", "R20", "R21"],
        "交互式 Agent、工具与多智能体环境": ["R14", "R19", "R22", "R23", "R24", "R25", "R26", "R27"],
        "系统、微服务与 LLM Serving 遥测": ["R02", "R12", "R15", "R16", "R17", "R28", "R29", "R30"],
    }
    by_id = {p["id"]: p for p in PAPERS}
    sections = []
    for name, ids in groups.items():
        rows = "\n".join(f"- [{pid} {by_id[pid]['title']}](./{pid}_{by_id[pid]['slug']}/README.md)" for pid in ids)
        sections.append(f"## {name}\n\n{rows}\n")
    local_rows = []
    for item in manifest:
        size = item["bytes"] / 1024 / 1024
        digest = item.get("sha256") or item.get("sha256_tree")
        local_rows.append(f"| [{item['name']}](./shared_data/{item['name']}) | {item['file_count']} | {size:.2f} MiB | `{digest}` | {', '.join(item['papers'])} |")
    index = f"""# Reference paper 实验数据目录

整理日期：{RETRIEVED_AT}

本目录覆盖 `literature_index.md` 中 R01–R30。每篇论文都有独立文件夹和 `README.md`；相同数据只在 `shared_data/` 保存一次，论文文档以相对链接引用。

下载策略：压缩包或可核验本地快照不超过 100 MiB 时下载；大型、受限、未发布或依赖在线环境的数据只记录官方入口。`VERIFIED`、`INFERRED`、`UNVERIFIED`、`AUTHOR_INPUT_NEEDED` 的含义沿用仓库研究规范。

{chr(10).join(sections)}

## 已保存的本地数据快照

| 名称 | 文件数 | 大小 | SHA-256/目录树 SHA-256 | 关联论文 |
|---|---:|---:|---|---|
{chr(10).join(local_rows)}

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
"""
    (ROOT / "README.md").write_text(index, encoding="utf-8")


def main() -> None:
    for paper in PAPERS:
        write_paper(paper)

    manifest = []
    for name, meta in SOURCES.items():
        path = SHARED / name
        if not path.exists():
            raise FileNotFoundError(f"Expected local dataset is missing: {path}")
        item = {"name": name, "retrieved_at": RETRIEVED_AT, **meta, **describe_path(path)}
        manifest.append(item)
    (ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    build_index(manifest)


if __name__ == "__main__":
    main()
