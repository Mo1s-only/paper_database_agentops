# Watson 实验目录

本目录把 Watson 的实验实现、测试、结果和说明分开保存。

## 目录

- `source/upstream/`：根目录 Watson 中的复现源码（当前为空或仅保留可迁移的上游材料）。
- `source/thesis_experiments/`：论文实验入口和 Watson 实现。
- `tests/upstream/`：根目录 Watson 中的测试代码（如有）。
- `tests/thesis_experiments/`：论文实验的离线/真实 demo 测试。
- `results/raw/`：从根目录 `Watson/out/` 整理来的原始运行结果、调用记录和报告。
- `results/upstream/`：预留给上游复现结果。
- `docs/upstream/`：根目录中的上游说明（如有）。
- `docs/thesis/`：实验设计、实验说明和项目 README。

结果中的 `calls.jsonl`、`api_trace.json` 等可能含有本地调用证据，分享前应先脱敏。此次整理没有重新运行模型实验，也没有改变结果内容。
