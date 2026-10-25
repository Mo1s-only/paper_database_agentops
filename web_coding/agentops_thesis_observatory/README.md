# AgentOps 实验工作台 · 重建版

本机实验平台：从真实输入定义出发，在 Ubuntu WSL 中执行已登记实验，将每次运行保存为独立记录，并展示 API 会话、AgentSight 系统观测、工具关联、Trace、SQLite 表格及图表。

完整的页面分区、字段含义、图表读法和操作步骤见[《页面说明与使用指南》](页面说明与使用指南.md)。

## 启动

在本目录的 PowerShell 中运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\Start-Observatory.ps1
```

默认地址 `http://127.0.0.1:8780/`。启动器会复用同一工作区的 2.0 服务；端口被其他程序占用时选择相邻可用端口，并打印实际地址。请使用新地址，旧版的 8766–8771 标签页已经停用。启动平台本身不消耗模型 API。

也可前台运行：

```powershell
python server.py --port 8780
```

需要 Python 3.12，后端使用标准库，无需 Node/npm 安装。页面和实验控制接口由同一个服务提供。

## 使用

1. 在运行列表选择一次历史或新运行；页面标题会显示精确 ID、时间、数据集及来源。
2. 总览查看 API 会话证据、系统数据库计数和各关联方法的结果；Trace、数据、文件页签查看该次运行的独立工件。
3. “新建实验”填写名称、实验类型与输入。输入说明明确它是受控任务定义、公开样本还是合成夹具，并提供原文件链接。
4. 运行预检，真实 API 实验确认本次调用范围后启动。后台自动调用 Ubuntu WSL，运行进度与新产生的证据自动刷新。
5. 同一数据集可以反复运行；每次获得新的 ID 和目录，历史结果可继续查看。

## 证据解释

- 真实跨层实验分别执行 Agent A、B 两个会话，每会话 CLI 软预算 $0.05。历史累计上限不再作为禁止重复的条件；每次运行记录自己的费用与调用确认。CLI 软预算与 CLI 报告费用均不是供应商最终账单。
- 真实实验优先复用历史成功运行的 Windows CurrentUser DPAPI 凭据别名 `test` 及其模型设置，凭据通过进程环境交给 WSL；页面仅显示别名与提供方信息。预检检查解密和转发，不向供应商发出试探请求。
- “API 会话”来自该次会话摘要及 SQLite LLM HTTP 记录；摘要缺失时显示未知。
- `session-and-tool` / `shared-tool-id` 衡量原生工具 ID 与系统语义记录的匹配。`process-and-tool` 与受控 Bash hook → eBPF 进程桥分别展示。
- 应用侧场景评分来自运行自己的验证报告，成功执行实验与任务中观察到预设故障是不同字段。
- Trace 来源会标为原生事件或控制器生命周期；缺少原生事件时只展示已有来源，不生成假 Span。
- 公开数据输入复核属于零 API 结构检查，不等同于重新采集公开数据集的原始系统运行。

默认历史样本 `real-canary-20261022-45`：`error-propagation-v1` 的两个真实会话成功，原生/系统工具 ID 4/4，`session-and-tool` accepted 4/4。Bash 受控进程桥为 2/2；Write 没有独立进程桥。详见该运行的原始场景报告和关联报告。

## 文件与数据

```
backend/data.py       数据集、历史运行索引、独立证据读取、SQLite 预览
backend/runner.py     固定实验配方、WSL 执行、预检和持久化进度
backend/server.py     本机 HTTP API
web/                 浏览器界面
server.py            服务入口
Start-Observatory.ps1 Windows 启动器
runtime/             本机索引和服务日志（不纳入 Git）
```

新实验工件保存在论文工作区的 `lab/experiment/observatory_runs/<run-id>/`。历史导入读取 `lab/experiment/` 中现有运行，源文件不变；工作台目录重建后可重新索引这些实验。页面的原文件接口仅提供登记数据集或所选运行目录内支持的工件，SQLite 以只读模式查询。

重建前的整套平台已移至 `web_coding/_archive/agentops_thesis_observatory_20261023_before_rebuild/`。本目录不依赖归档代码。
