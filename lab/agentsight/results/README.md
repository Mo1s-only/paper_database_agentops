# AgentSight 实验结果组织规则

本目录将“实验结论”与“原始运行产物”分开保存，且每次实验使用独立的实验 ID，禁止把两次运行追加到同一份结果文档中。

## 目录结构

```text
results/
├── README.md
├── AgentSight输出数据说明.md       # 跨实验通用的字段和文件说明
├── experiments/                     # 可追溯的独立实验结论
│   └── <experiment_id>/
│       └── 实验结果.md
├── runs/                            # 本地原始产物，默认不提交 Git
│   └── <experiment_id>/
│       ├── session.db
│       ├── record.log
│       ├── report-*.txt
│       └── ...
└── upstream/                        # 2026-09-14 导入的历史材料
```

`upstream/session` 与 `upstream/test-out` 是同一次历史实验的两份保存副本，不计为两次独立实验。新实验不再写入 `upstream/`。

## 实验 ID

命名格式：

```text
YYYYMMDDTHHMMSS_<experiment_name>
```

例如：

```text
20260923T145844_agentsight_e2e
```

一个实验 ID 只能对应一次真实执行、一份原始结果和一份结论文档。

## 当前实验索引

| 实验 ID | 状态 | 用途 | 结果文档 |
|---|---|---|---|
| `20260923T141354_agentsight_e2e` | `VERIFIED` | P0 修复前基线复现 | [实验结果](experiments/20260923T141354_agentsight_e2e/实验结果.md) |
| `20260923T145844_agentsight_e2e` | `VERIFIED` | 一键复现脚本实测 | [实验结果](experiments/20260923T145844_agentsight_e2e/实验结果.md) |

## 每次实验必填字段

每份 `实验结果.md` 至少记录：

- 实验 ID、时间、目的和环境；
- 执行命令与成功标准；
- 核心数量结果；
- `VERIFIED`、`INFERRED`、`UNVERIFIED` 证据边界；
- 原始结果目录；
- 失败项、异常和下一研究闸门。

不得在文档中记录 API key、Authorization header 或未脱敏的私密 Prompt。
