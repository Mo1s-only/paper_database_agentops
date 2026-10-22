# AgentOps Thesis Observatory

面向论文实验的本地 AgentOps 可观测性与实验控制台。页面结构借鉴常见 Trace、Evaluation 和 Evidence 控制台，但视觉、文案与交互均为本项目独立实现。控制接口只绑定 `127.0.0.1`，不能作为公网服务部署。

## 数据更新

在仓库根目录执行：

```powershell
python web_coding/agentops_thesis_observatory/scripts/build_data.py
python web_coding/agentops_thesis_observatory/scripts/validate_site.py
```

`build_data.py` 读取仓库内已存在的实验 JSON、公开样本与离线 fixture，并生成 `dist/data.json`；不会发起网络请求。页面不会把 `INFERRED`、`UNVERIFIED` 或 `BLOCKED` 状态显示成完成。

## 本地启动与页面操作

在 `web_coding/agentops_thesis_observatory/` 目录启动：

```powershell
python scripts/local_controller.py
```

打开 `http://127.0.0.1:8766/#experimentSetup`。填写名称、类型和本次输入数据集后，可以从页面保存/载入草稿、运行预检、启动实验、查看阶段进度和结果、停止后续 API 阶段、查看历史运行及刷新证据快照。若双 Agent 会话成功且费用完整、但系统工具捕获不完整导致 AgentRx 尚未执行，可在历史记录中选择该批次、再次勾选预算确认后点“继续未执行的 AgentRx”；这只完成原批次的第三阶段，不重跑前两次会话。每次保存草稿后重置数据集选择，避免误沿用。浏览器草稿本身不运行实验、不授权 API 调用。

页面接口：`GET /api/health`、`GET /api/preflight?dataset_id=...`、`GET /api/runs`、`GET /api/runs/{id}`、`POST /api/runs`、`POST /api/runs/{id}/stop-after-current`、`POST /api/runs/{id}/continue-agentrx`、`POST /api/refresh-snapshot`。POST 使用同源 JSON 与 `X-AgentOps-Control: 1`，不接受任意命令、脚本路径或数据集路径。运行工件保存在 `lab/experiment/experiment_20261019_18/results/run-*/`；原始 CLI 日志不会经 HTTP 返回。

当前付费授权仅允许 `error-propagation-v1` 两会话后接一条 AgentRx #12 诊断；预检检查 WSL Ubuntu root、运行工具和凭据存在、预算数值、历史账本政策及工作区可访问性。用户已为 `2026-10-19` 这一批次明确批准使用 `$2.183708` 冻结账本作为未完全复核的历史基线，原始路径仍是 0/30；这一例外不适用于其他批次。批次规划 1.80 CNY、上限 2 CNY，不自动重试。页面的“停止后续 API 阶段”不会中断当前已开始的会话，但会禁止下一阶段启动。其他付费数据集显示为未授权，不会运行。公开数据与合成 fixture 的页面操作是零 API 的**已有标准化输入结构复核**，不是上游 adapter 重跑、真实系统采集或归因准确率评估。

Ubuntu WSL2、Claude Code 和 AgentSight 已在本机就绪；控制器从同级 `agentsight/test/.env` 读取已有凭据，不在页面显示密钥。授权批次 `run-dff396441f6a` 已执行 3 个真实 CLI 会话，CLI 报告合计 `$0.1147568`（内部规划系数下约 `¥1.147568`）；页面状态 `PARTIAL`，因为 AgentSight 的工具记录为 0/4，不能据此声称系统层归因成功。详见 `lab/experiment/experiment_20261019_18/实验记录.md`。可运行 `python -m unittest discover -s scripts -p test_local_controller.py -v` 验证控制器。

数据集目录从本地受控场景代码、AgentRx 公开样本、公开数据适配报告和合成 fixture 构建。已有实验若无可验证的输入数据集记录，表中显示“未登记”；计划输入明确标为“计划”，不视作已执行。

## 文件

- `dist/index.html`：页面结构；
- `dist/styles.css`：响应式视觉系统；
- `dist/app.js`：图表、筛选、Trace inspector 和交互；
- `dist/data.json`：由实验工件生成的数据快照；
- `scripts/local_controller.py`：本机受控实验接口与运行器；
- `.openai/hosting.json`：Sites 私有部署配置。
