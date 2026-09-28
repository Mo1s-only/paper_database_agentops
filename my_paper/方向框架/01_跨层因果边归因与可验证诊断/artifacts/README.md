# Artifacts 清单

本目录保存制品清单与冻结版本说明，不保存大型原始数据。

建议登记：

- `schema_version`：统一事件 schema 版本；
- `code_commit`：`my_paper_coding/` 中实现的 Git 提交；
- `dataset_manifest`：trace ID、任务、框架、故障、真值、脱敏状态；
- `experiment_ids`：指向 `lab/*/results/experiments/`；
- `environment_lock`：模型、端点、依赖、OS/WSL/内核、Agent 工具版本；
- `analysis_scripts`：统计、绘图和表格生成入口；
- `release_policy`：公开、受限、仅本地三档。

最小复现包应能从一组脱敏 trace 重新生成主表、主要图和失败样本索引。
