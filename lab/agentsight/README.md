# AgentSight 实验目录

本目录将 AgentSight 的源码、测试和结果分开保存，避免把运行产物混入源码。

## 目录

- `source/upstream/`：根目录 `agentsight/` 的源码快照；不包含其内部 `.git`。
- `source/thesis_adapter/`：原有 `lab/agentsight/` 中的论文适配与整理代码。
- `tests/upstream/`：根目录 `agentsight/test/` 的测试脚本和说明；真实 `.env` 不纳入整理。
- `results/upstream/`：已有 AgentSight 结果材料（若存在）。
- `docs/`：实验说明和来源记录。

来源：AgentSight 上游仓库为 `https://github.com/eunomia-bpf/agentsight.git`；原根目录快照的上游提交为 `bb99b66f8f98e4b9f8b1769a3da0a8fbbe26b6c3`。本次整理只改变目录位置，不声称重新运行了实验。
