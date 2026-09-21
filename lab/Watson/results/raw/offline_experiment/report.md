# Watson 离线实验结果

本轮是确定性假客户端的控制流与故障注入实验，不能作为真实模型准确率、解释忠实性或论文效果复现的证据。

| 场景 | k | 尝试数 | 匹配数 | 接受数 | 请求总数 | 状态 |
|---|---:|---:|---:|---:|---:|---|
| accept | 1 | 1 | 1 | 1 | 5 | complete |
| accept | 3 | 3 | 3 | 3 | 9 | complete |
| accept | 5 | 5 | 5 | 5 | 13 | complete |
| accept | 10 | 10 | 10 | 10 | 23 | complete |
| wrong | 1 | 4 | 0 | 0 | 6 | insufficient_candidates |
| wrong | 3 | 12 | 0 | 0 | 14 | insufficient_candidates |
| wrong | 5 | 20 | 0 | 0 | 22 | insufficient_candidates |
| wrong | 10 | 40 | 0 | 0 | 42 | insufficient_candidates |
| judge_reject | 1 | 4 | 4 | 0 | 10 | insufficient_candidates |
| judge_reject | 3 | 12 | 12 | 0 | 26 | insufficient_candidates |
| judge_reject | 5 | 20 | 20 | 0 | 42 | insufficient_candidates |
| judge_reject | 10 | 40 | 40 | 0 | 82 | insufficient_candidates |
| alternating | 1 | 1 | 1 | 1 | 5 | complete |
| alternating | 3 | 5 | 3 | 3 | 11 | complete |
| alternating | 5 | 9 | 5 | 5 | 17 | complete |
| alternating | 10 | 19 | 10 | 10 | 32 | complete |

## 数据准入审计

```json
{
  "exists": true,
  "total": 3,
  "with_prompt": 0,
  "text_eligible": 0,
  "missing_request": 3,
  "database_unchanged": true
}
```

## 本轮修正与边界

- 对照 Watson.pdf 第 4 页 RepCoT 描述：候选生成不再看到目标输出；目标仅用于生成后的匹配筛选。
- 消融生成同样不再包含目标输出；无 FINAL 标记的结果不算匹配。
- 拒绝混合文本和工具调用记录；未配对记录跳过且不调用模型。
- 保存候选、匹配结果、judge verdict、请求数及包含消融在内的耗时；采样耗尽标记 insufficient_candidates。
- 当前使用严格文本匹配，原文使用语义等价 judge；单次离散消融也不等价于 PromptExp 概率归因。
- 消息角色被展平，镜像标记 approximate；尚未实现原文 top/bottom-n judge、token 计费及真实基准。
- 未检测到 WATSON 配置环境变量，本轮没有调用外部模型。
- 真实实验需先取得可配对的文本调用与模型端点、模型名及密钥，再开展 5 条试运行。
