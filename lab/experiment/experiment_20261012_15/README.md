# experiment_20261012_15｜观测模块严格质量门与确定性回放

## 目标

在不发起任何 API 调用的前提下，对 `experiment_20261012_14` 的真实协议 v0.2 事件执行更严格的模块级验证：

1. 为 AgentSight boot epoch 锚点加入系统时钟分辨率下界，保证未来不确定度不再记录为 0；
2. 将事件 ID 改为由稳定身份字段生成，使同一输入的离线回放字节级一致；
3. 按 session 统计 PID 映射的 `accepted / inferred / abstain` 覆盖率；
4. 对重复 ID、序列断裂、进程身份变化、生命周期缺失、时钟公式错误等无效输入执行负向验证；
5. 产出一个单命令、零网络的质量门报告。
6. 用本地受控 PID namespace 的 `/proc/*/status` `NSpid` 向量建立直接映射真值。

## 证据边界

- `VERIFIED`：输入来自已经保存的真实事件流；质量门执行过程不调用网络。
- `UNVERIFIED`：时钟分辨率下界的源码修复尚未经过新的真实 API 会话；本实验只能用本地 Rust 测试验证实现。
- `UNVERIFIED`：真实 PID 映射没有独立 namespace ground truth，覆盖率不等于准确率。

原始回放文件写入受 `.gitignore` 保护的 `results/`，可提交目录只保存计划和机器可读质量报告。

## 一键复现

在仓库根目录执行以下命令即可用临时目录完成两次回放、覆盖率统计和负向矩阵；命令不会写入仓库，也不会调用网络：

```powershell
python my_paper_coding/trace_adapter/observation_quality_gate.py --input lab/experiment/experiment_20261012_14/results/application-events-v0.2.jsonl
```

受控 PID namespace 真值可在支持 user namespace 的 Linux/WSL 环境中用以下命令重新生成；`--output` 必须指向一个尚不存在的文件：

```powershell
wsl -d Ubuntu python3 /mnt/c/Users/mobao/Desktop/论文方向/my_paper_coding/trace_adapter/pid_namespace_fixture.py --output /tmp/agentops-pid-namespace.json
```
