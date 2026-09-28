# P0 请求—响应配对

本目录用于验证 AgentSight 能否将同一次 LLM 调用的 request 与 response 稳定关联。

当前质量门槛：

- 配对 Precision 不低于 0.95；
- 不确定的配对必须标记或舍弃；
- 不允许仅根据“最近时间戳”强行配对；
- 实验输出不得包含 API 密钥。

`capture_claude_http.sh` 会用唯一 marker 发起一次真实 Claude Code 调用，并保存 AgentSight HTTP 解析事件。凭据文件通过环境变量传入，不写入仓库。

```bash
P0_ENV_FILE=/path/to/local/.env \
P0_OUT_DIR=/path/to/dedicated/run \
./capture_claude_http.sh
```

原始 HTTP 内容可能包含 prompt 和 response，仅保存在本地实验目录，不应提交。

## Pilot 批量实验与判定

先设置本地凭据路径和结果目录，再运行 5 条带唯一 marker 的调用：

```bash
P0_ENV_FILE=/path/to/local/.env \
P0_OUT_BASE=/path/to/local/p0-results \
P0_COUNT=5 \
./run_pilot_batch.sh
```

`analyze_pairing.py` 只接受以下证据作为一条 marker 配对：

1. 请求体包含本轮 marker；
2. SSE 响应文本包含同一 marker；
3. 请求和响应具有相同的观测 `pid/tid`；
4. 响应时间不早于请求时间。

输出中的 `marker_pair_precision` 和 `marker_pair_recall` 只表示本轮 marker 的受控配对结果，不代表所有请求的通用配对性能。`gate_pass` 通过后，才进入带失败标签的跨层归因 pilot。

## 外部轨迹适配

`adapt_traceelephant.py` 读取 TraceElephant 的公开 `trace_metadata.json` 与 `step_records.json`，生成本地统一 schema。映射细节和证据边界见 `public_data_mapping.md`。适配代码不会把外部 Agent/Step 标签伪装成 AgentSight 的系统层事件。
