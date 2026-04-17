# docs/design/memory-system — 内存系统设计

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-04-16 | 初始版本 | Gemini CLI |

## 文档列表

- [DETAILED_DESIGN.md](DETAILED_DESIGN.md) — SQLite + 向量检索存储设计

## 模块概述

该模块负责 Agent 的长期记忆，通过 `BAAI/bge-m3` 模型实现语义检索。
