# experiment_20261016_17：真实API调用逐次审计

本轮不发起网络调用，只对全仓已保存的DeepSeek调用按provider session ID去重并逐条整理。

- 详细文档：[真实API调用逐次审计.md](真实API调用逐次审计.md)
- 机器可读结果：[api-call-audit.json](api-call-audit.json)
- 生成脚本：`my_paper_coding/experiment_control/build_api_call_audit.py`
- 结果：30个会话，29个成功，累计2.183708 USD，网络调用0次。
