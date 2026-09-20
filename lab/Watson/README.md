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
python Watson\test_watson.py
```

## 从 AgentSight 会话导出

```powershell
python Watson\watson.py export `
  --db agentsight\test\out\session.db `
  --output Watson\out\calls.jsonl
```

已有测试样例包含工具调用，且当前数据库缺少配对 request；它只用于证明 response 证据提取正确。请在完成 request-response 配对后，为真实 RepCoT 选择输出为纯文本的调用。

## 真实旁路重建（会调用模型）

提供 OpenAI 兼容 endpoint、模型和 key；模型、temperature、top-p 应与 primary 完全一致，或在报告中标作近似镜像：

```powershell
$env:WATSON_API_KEY = '...'
python Watson\watson.py reconstruct `
  --input Watson\out\calls.jsonl `
  --output Watson\out\report.json `
  --base-url https://your-openai-compatible-endpoint/v1 `
  --model your-primary-model --samples 10 --temperature 0 --top-p 1
```

该命令会产生 API 费用；程序在报告中保存请求数、候选接受率、耗时及失败原因，便于复现实验的成本核算。

## 产物

- `calls.jsonl`：脱敏前的本地证据 manifest，**不得提交或分享**。
- `report.json`：重建、验证和汇总的全部可追溯记录。
- `test_watson.py`：用假客户端进行端到端、不依赖网络的回归测试。

## 2026-09-20 实验更新

在 Watson 目录执行 `python run_offline_experiment.py`，运行 k=1/3/5/10 × 四种确定性故障场景，共 16 组离线实验。结果见 `out/offline_experiment/report.md` 与 `results.json`。

已修正 RepCoT 与消融提示中的目标答案泄漏。生成阶段只给原输入，生成后才匹配目标输出。当前是近似实现：严格文本匹配替代原文语义等价判定、单次离散消融替代 token 概率归因、消息角色展平且没有完整解码配置重放，故所有结果标为 approximate。当前 judge 尚未实现原文 top/bottom-n 验证。

本轮数据审计：3 条调用均缺失 request，真实实验可用样本为 0。没有发起真实模型请求；离线通过仅证明控制流按预期工作。

## 真实 DeepSeek demo（单次预算低于 ¥0.50）

在 Watson 目录运行 `python run_real_demo.py`，根据隐藏提示输入名称为 Watson 的 API 密钥。程序调用 `deepseek-v4-flash`（官方当前路由到 V4.1-Flash），运行两个真实文本决策任务与 Watson 旁路流程。最多 24 次请求，每次 256 输出 tokens；按当前高峰价格预留总上限 ¥0.313728，预算阈值 ¥0.40，无自动重试。

结果逐次保存在 `out/real_demo/<UTC时间戳>/report.md`。详细步骤、模型、费用假设与限制见 `实验说明.md`。真实 demo 应使用这个带预算保护的入口；旧的通用 reconstruct 命令没有相同费用约束。
