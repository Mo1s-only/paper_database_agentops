# AgentOps Thesis Observatory

面向论文实验的静态 AgentOps 可观测性仪表盘。页面结构借鉴常见 Trace、Evaluation 和 Evidence 控制台，但视觉、文案与交互均为本项目独立实现。

## 数据更新

在仓库根目录执行：

```powershell
python web_coding/agentops_thesis_observatory/scripts/build_data.py
python web_coding/agentops_thesis_observatory/scripts/validate_site.py
```

`build_data.py` 只读取 `lab/experiment/` 中已经存在的 JSON 证据，并生成 `dist/data.json`。页面不会把 `INFERRED`、`UNVERIFIED` 或 `BLOCKED` 状态显示成完成。

## 文件

- `dist/index.html`：页面结构；
- `dist/styles.css`：响应式视觉系统；
- `dist/app.js`：图表、筛选、Trace inspector 和交互；
- `dist/data.json`：由实验工件生成的数据快照；
- `.openai/hosting.json`：Sites 私有部署配置。
