# Agent 实验成本控制

本目录只读取已有本地日志和实验计划，不主动调用模型 API。

## 成本账本

```powershell
python .\cost_ledger.py `
  --root ..\failure_pilot\results `
  --json-out .\cost-ledger-20260928.json `
  --markdown-out .\cost-ledger-20260928.md
```

## 下一轮预算预检

```powershell
python .\budget_guard.py `
  --manifest .\next-real-experiment-plan.json `
  --ledger .\cost-ledger-20260928.json `
  --max-usd 1.00
```

预算检查只输出 `PASS` 或 `BLOCKED`，不会启动 Claude、AgentSight 或任何网络请求。
