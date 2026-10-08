# Tools Fail 论文精读笔记

## 论文信息

- 标题：Tools Fail: Detecting Silent Errors in Faulty Tools
- 作者：Jimin Sun、So Yeon Min、Yingshan Chang、Yonatan Bisk
- Venue/年份：EMNLP 2024 Main
- 官方来源：[ACL Anthology](https://aclanthology.org/2024.emnlp-main.790/)
- 本地论文：`Tools_Fail_Detecting_Silent_Errors_in_Faulty_Tools_EMNLP2024.pdf`
- 阅读目的：静默工具错误、工具契约和错误检测
- 状态：精读；发表状态 `VERIFIED`

## 1. One-sentence contribution

Tools Fail 建立工具错误分类并研究 LLM 是否能发现没有显式异常信号、但会破坏任务结果的 silent tool errors。

## 2. Problem setting

论文区分工具输入错误、上下文错误和工具自身输出错误。重点是工具返回格式合法但内容错误的情况，例如 broken calculator 或视觉工具把 tomato 识别成 apple，后续 Agent 仍可能过度信任结果并产生错误动作。

## 3. Method core

作者将工具使用抽象为任务输入、工具输入、上下文、工具输出和最终任务结果，并用 oracle 输出定义工具偏差。实验测试模型是否能识别错误工具结果，再研究 disclaimer、confidence 和 checklist 等 in-context intervention。论文重点是检测，明确把故障归因和恢复留作后续问题。

## 4. Evidence

- 受控 calculator 场景：将正确结果替换为无显式报错的错误结果。
- ALFRED 具身任务：使用对象检测和动作规划产生自然工具错误及错误级联。
- 研究错误偏差大小、模型置信度、上下文和干预提示对检测的影响。

证据位置：摘要、§3 Background and Problem Definition、§6 Broken Calculator、§8 Natural Tool Errors: ALFRED、§9 Conclusion。

## 5. Limitations

论文主要研究“工具错误是否被发现”，不是哪个 Agent 或哪条消息边承担责任。错误 oracle 在受控任务中容易获得，真实开放环境中的工具契约和任务关键性更难判断。

## 6. Use for my thesis

你的 `inventory-silent-tool` 案例与该问题高度相关，但不能把工具输出错误直接等同于 Agent B 的决定性责任。Adapter 应保存工具输入、原始输出、退出码、契约和任务 oracle；归因器还要判断错误是否被后续 Agent 修复或放大。

## 7. Claim–evidence rows

| Claim | Evidence | Status |
|---|---|---|
| 合法格式的工具返回仍可能破坏任务 | broken calculator、ALFRED | `VERIFIED` |
| 工具错误检测是归因和恢复的前置步骤 | 引言和结论 | `VERIFIED` |
| 工具返回错误即可认定责任 Agent | 论文没有这样定义 | `UNVERIFIED` |
