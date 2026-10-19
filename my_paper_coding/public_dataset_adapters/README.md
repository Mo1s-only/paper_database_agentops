# 公开归因数据适配器

本目录把 Who&When、TRAIL、AgentTrace 转换为统一的归因前记录：

```text
run/session → agent → step/span → relation → label/evidence
```

统一 schema 位于 [`schema/attribution-benchmark-record-v0.1.schema.json`](schema/attribution-benchmark-record-v0.1.schema.json)，五类真值和拒绝规则见 [`ground_truth_protocol.md`](ground_truth_protocol.md)。适配器不会运行LLM或归因算法，也不会把缺失的责任边和路径补造出来。

从仓库根目录运行：

```powershell
python -m my_paper_coding.public_dataset_adapters.cli `
  --who-when "Reference paper/datasets/shared_data/WhoAndWhen_184" `
  --trail "Reference paper/datasets/shared_data/TRAIL_benchmarking_148_traces.zip" `
  --agenttrace "Reference paper/datasets/shared_data/AgentTrace_ICLR2026_data" `
  --output "lab/experiment/<experiment>/results"
```

输出目录必须不存在，防止覆盖已有实验。输出包含三个JSONL、机器可读兼容性报告和Markdown报告。关系重建率、证据完整率和拒绝率的定义固定在真值协议中。
