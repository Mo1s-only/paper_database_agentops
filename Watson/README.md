# Watson × AgentSight：认知观测复现

这是 Watson 的**可审计 RepCoT 主链路复现**，以 AgentSight 已保存的 SQLite 会话库为只读输入。它不修改被观测 Agent，也不会出现在主 Agent 的关键路径中。

> 已知的观测前置条件：当前 `agentsight/test/out/session.db` 有 response，但其 `request_body_json` 为空。导出器会保留该事实，真实重建会跳过这些不完整记录，绝不拿不配对的输入/输出伪造“复现成功”。P0 的首要工作是将 AgentSight 原始 TLS 请求事件和对应响应按连接/消息 ID 可靠落库。

## 覆盖范围

- 已实现：AgentSight `llm_calls` 提取；request / response 规范化；镜像配置 manifest；RepCoT 候选生成与目标输出筛选；PromptExp 风格组件消融接口；LLM judge；元推理汇总；结构化 JSON 报告；离线端到端测试。
- 限制：FIM 仅在模型 API 支持 prefix/suffix 时可实现；默认 RepCoT。对 API 无 token logprob 的模型，组件消融使用“移除组件后目标输出是否仍可复现”的离散影响量，而非论文的精确 token 概率差；报告会明确标记为 `match_ablation`。
- 真实运行只支持**文本型 completion**。工具调用中间轮次会被导出但标为不支持，避免伪造输出匹配。

## 快速验证（零 API、零费用）

```powershell
cd C:\Users\mobao\Desktop\论文方向
python Watsom\test_watson.py
```

## 从 AgentSight 会话导出

```powershell
python Watsom\watson.py export `
  --db agentsight\test\out\session.db `
  --output Watsom\out\calls.jsonl
```

已有测试样例包含工具调用，且当前数据库缺少配对 request；它只用于证明 response 证据提取正确。请在完成 request-response 配对后，为真实 RepCoT 选择输出为纯文本的调用。

## 真实旁路重建（会调用模型）

提供 OpenAI 兼容 endpoint、模型和 key；模型、temperature、top-p 应与 primary 完全一致，或在报告中标作近似镜像：

```powershell
$env:WATSON_API_KEY = '...'
python Watsom\watson.py reconstruct `
  --input Watsom\out\calls.jsonl `
  --output Watsom\out\report.json `
  --base-url https://your-openai-compatible-endpoint/v1 `
  --model your-primary-model --samples 10 --temperature 0 --top-p 1
```

该命令会产生 API 费用；程序在报告中保存请求数、候选接受率、耗时及失败原因，便于复现实验的成本核算。

## 产物

- `calls.jsonl`：脱敏前的本地证据 manifest，**不得提交或分享**。
- `report.json`：重建、验证和汇总的全部可追溯记录。
- `test_watson.py`：用假客户端进行端到端、不依赖网络的回归测试。
