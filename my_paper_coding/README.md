# My Paper Coding

用于保存毕业论文自己的实验代码、数据处理脚本、评测脚本和原型实现。

建议结构：

```text
my_paper_coding/
  p0_pairing/        # AgentSight 请求—响应配对 pilot
  failure_pilot/     # 带独立责任真值的受控失败 pilot
  README.md
```

当前研究代码：

- `p0_pairing/`：唯一 marker 的请求—响应配对分析；原始调用结果在被忽略的 `results/` 下保存。
- `failure_pilot/`：确定性两 Agent 故障、统一轨迹、责任真值和离线归因评分；不依赖网络或模型 API。

提交实验结果前，说明：

- 实验目的；
- 输入数据或任务；
- 运行命令；
- 关键指标；
- 输出文件；
- 当前结论和局限。

