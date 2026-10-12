# API 成本账本

> 仅解析本地 Claude JSON 日志，本次生成没有发起 API 请求。相同 session ID 的重复文件只计一次，并保留重复路径。

- 扫描文件数：33
- 可计价记录数：31
- 重复 session 记录数：1
- 去重后运行数：30
- 累计成本（USD）：2.183708
- 单次最高成本（USD）：0.137935

| 日志 | 模型 | 成本 USD | 输入 token | 输出 token |
|---|---|---:|---:|---:|
| `lab\agentsight\results\runs\20260923T141354_agentsight_e2e\claude-run.log` | deepseek-v4-pro | 0.135960 | 22580 | 214 |
| `lab\agentsight\results\runs\20260923T145844_agentsight_e2e\claude-run.log` | deepseek-v4-pro | 0.137935 | 22578 | 291 |
| `lab\agentsight\results\runs\20260928T105904_agentsight_e2e\claude-run.log` | deepseek-v4-pro | 0.122847 | 19321 | 274 |
| `lab\agentsight\results\upstream\session\claude-run.log` | deepseek-v4-pro | 0.136117 | 22529 | 228 |
| `lab\experiment\experiment_20261010_14\results\framework-native.jsonl` | deepseek-v4-pro | 0.024657 | 3798 | 155 |
| `lab\experiment\experiment_20261010_15\results\framework-native.jsonl` | deepseek-v4-pro | 0.024867 | 3805 | 162 |
| `lab\experiment\experiment_20261012_14\results\framework-native.jsonl` | deepseek-v4-pro | 0.024832 | 3803 | 161 |
| `my_paper_coding\failure_pilot\results\agentsight-attach-20260928\claude-run.log` | deepseek-v4-pro | 0.095757 | 16318 | 239 |
| `my_paper_coding\failure_pilot\results\agentsight-two-agent-20260928\claude-agent-a.log` | deepseek-v4-pro | 0.095422 | 16426 | 204 |
| `my_paper_coding\failure_pilot\results\agentsight-two-agent-20260928\claude-agent-b.log` | deepseek-v4-pro | 0.122589 | 16683 | 566 |
| `my_paper_coding\failure_pilot\results\real-canary-20260929\claude-agent-a.log` | deepseek-v4-pro | 0.071722 | 16134 | 198 |
| `my_paper_coding\failure_pilot\results\real-canary-20260929\claude-agent-b.log` | deepseek-v4-pro | 0.087142 | 16520 | 559 |
| `my_paper_coding\failure_pilot\results\real-canary-20260929-ubuntu24\claude-agent-a.log` | deepseek-v4-pro | 0.094517 | 16360 | 181 |
| `my_paper_coding\failure_pilot\results\real-canary-20260929-ubuntu24\claude-agent-b.log` | deepseek-v4-pro | 0.123229 | 16681 | 592 |
| `my_paper_coding\failure_pilot\results\real-pilot-inventory-20260928\claude-agent-a.log` | - | 0.000000 | 0 | 0 |
| `my_paper_coding\failure_pilot\results\real-pilot-inventory-20260928-r2\claude-agent-a.log` | deepseek-v4-pro | 0.095687 | 16419 | 216 |
| `my_paper_coding\failure_pilot\results\real-pilot-inventory-20260928-r2\claude-agent-b.log` | deepseek-v4-pro | 0.123159 | 16757 | 574 |
| `my_paper_coding\p0_pairing\results\20260928T031958Z_p0_pairing_pilot_01\claude.json` | deepseek-v4-pro | 0.082540 | 16213 | 59 |
| `my_paper_coding\p0_pairing\results\20260928T032023Z_p0_pairing_pilot_02\claude.json` | deepseek-v4-pro | 0.082620 | 16214 | 62 |
| `my_paper_coding\p0_pairing\results\20260928T032046Z_p0_pairing_pilot_03\claude.json` | deepseek-v4-pro | 0.081970 | 16214 | 36 |
| `my_paper_coding\p0_pairing\results\20260928T032109Z_p0_pairing_pilot_04\claude.json` | deepseek-v4-pro | 0.081970 | 16214 | 36 |
| `my_paper_coding\p0_pairing\results\20260928T_p0_pairing_pilot_01\claude.json` | deepseek-v4-pro | 0.082345 | 16214 | 51 |
| `my_paper_coding\trace_adapter\real_application_runs\real-application-20261010\claude-agent-a.log` | deepseek-v4-pro | 0.022047 | 3070 | 209 |
| `my_paper_coding\trace_adapter\real_application_runs\real-application-20261010\claude-agent-b.log` | deepseek-v4-pro | 0.040432 | 4758 | 402 |
| `my_paper_coding\trace_adapter\real_application_runs\real-complete-20261010\claude-agent-a.log` | deepseek-v4-pro | 0.020137 | 3013 | 144 |
| `my_paper_coding\trace_adapter\real_application_runs\real-complete-20261010\claude-agent-b.log` | deepseek-v4-pro | 0.033318 | 4110 | 352 |
| `my_paper_coding\trace_adapter\real_application_runs\real-error-propagation-20261010\claude-agent-a.log` | deepseek-v4-pro | 0.035867 | 4002 | 473 |
| `my_paper_coding\trace_adapter\real_application_runs\real-error-propagation-20261010\claude-agent-b.log` | deepseek-v4-pro | 0.034668 | 4120 | 404 |
| `my_paper_coding\trace_adapter\real_application_runs\real-routing-error-20261010\claude-agent-a.log` | deepseek-v4-pro | 0.036272 | 4088 | 472 |
| `my_paper_coding\trace_adapter\real_application_runs\real-routing-error-20261010\claude-agent-b.log` | deepseek-v4-pro | 0.033083 | 4003 | 364 |
