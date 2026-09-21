# Lab 实验材料

`lab/` 保存第三方项目复现、论文实验源码、测试代码和结果材料。

当前实验按以下层级组织：

```text
lab/
├── agentsight/
│   ├── source/       # upstream 与 thesis_adapter
│   ├── tests/        # upstream 测试
│   ├── results/      # 运行结果
│   └── docs/         # 来源和实验说明
└── Watson/
    ├── source/       # upstream 与 thesis_experiments
    ├── tests/        # upstream 与 thesis_experiments 测试
    ├── results/      # 原始运行结果
    └── docs/         # 实验说明
```

`source`、`tests` 和 `results` 的内容不应互相混放。真实 API 输出、数据库、日志和密钥在提交前必须检查脱敏状态。
