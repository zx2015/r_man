# docs/design/memory-system — 长期记忆系统设计

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-04-17 | 初始版本 | Gemini CLI |

## 设计列表

- [DETAILED_DESIGN.md](DETAILED_DESIGN.md) — SQLite+vec 虚拟表 Schema、脱敏摘要算法及自动维护策略。

## 模块概述
该模块负责 Agent 的跨对话记忆。核心通过 LLM 蒸馏出不含隐私的摘要，并利用向量搜索实现语义层面的背景召回。
